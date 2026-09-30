param(
    [string]$Bucket = "aero-governed-blockers-988177451335-20260919",
    [string]$Project = "",
    [string]$Zone = "us-central1-b"
)

$ErrorActionPreference = "Stop"
$study = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$p11 = Join-Path $study "phase11"
$cfgPath = Join-Path $p11 "configs\phase11_iterative_optimization.json"
$startupPath = Join-Path $p11 "optimization\phase11_worker_startup.sh"
$cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json
$budget = $cfg.cloudBudget
if ([double]$budget.maximumNewAggregateUsd -gt [double]$budget.approvedRemainingUsd -or
    [int]$budget.maxInstancesTotal -ne 1 -or [int]$budget.maxRunDurationSeconds -gt 600) {
    throw "Phase-11 new-cloud cap/time/instance guard does not match the approved remaining budget."
}
if (-not $Project) { $Project = (& gcloud config get-value project 2>$null).Trim() }
if (-not $Project) { throw "No active GCP project is configured." }

$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$instance = "hsedf-p11-$($runId.ToLower().Replace('t','-').Replace('z',''))"
$prefix = "highspeed-edf-phase11-$runId"
$bundleName, $resultName = "$prefix-input.tar.gz", "$prefix-output.tar.gz"
$logName, $failureName, $finishName = "$prefix-worker.log", "$prefix-failure.log", "$prefix-output-finish.json"
$bundlePath = Join-Path $p11 "results\phase11_bundle.tar.gz"
$resultPath = Join-Path $p11 "results\phase11_cloud_output.tar.gz"
$workerLogPath = Join-Path $p11 "results\phase11_worker.log"
$finishPath = Join-Path $p11 "results\phase11_finish.json"
$submissionPath = Join-Path $p11 "results\phase11_submission.json"

Push-Location $study
try {
    & tar.exe -czf $bundlePath phase11\configs\phase11_iterative_optimization.json phase11\cases phase10\optimization\phase10_openfoam_worker.py
    if ($LASTEXITCODE -ne 0) { throw "Failed to package Phase-11 cases." }
} finally { Pop-Location }

$submission = [ordered]@{
    phase = 11; status = "staging"; runId = $runId; project = $Project; bucket = $Bucket
    instance = $instance; zone = $Zone; machineType = $budget.machineType
    provisioningModel = $budget.provisioningModel; maximumLifetimeSeconds = [int]$budget.maxRunDurationSeconds
    terminationAction = $budget.terminationAction; maxInstancesTotal = 1; maxConcurrentInstances = 1
    newAggregateCapUsd = [double]$budget.approvedRemainingUsd
    computeMaximumUsd = [double]$budget.computeMaximumUsd
    storageNetworkReserveUsd = [double]$budget.storageNetworkArtifactReserveUsd
    contingencyUsd = [double]$budget.contingencyUsd
    estimatedNewMaximumAggregateUsd = [double]$budget.maximumNewAggregateUsd
    phase10PriorEnvelopeEstimateUsd = 0.08414
    cases = @($cfg.cases | ForEach-Object { $_.id })
    actualBillingAmountUsd = $null
}
$submission | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $submissionPath -Encoding UTF8

$created = $false
$deleted = $false
$start = $null
try {
    & gcloud storage cp $bundlePath "gs://$Bucket/$bundleName"
    if ($LASTEXITCODE -ne 0) { throw "Could not stage Phase-11 inputs." }
    & gcloud compute instances create $instance `
        --project=$Project `
        --zone=$Zone `
        --machine-type=$($budget.machineType) `
        --provisioning-model=SPOT `
        --instance-termination-action=DELETE `
        --max-run-duration=$($budget.maxRunDurationSeconds)s `
        --boot-disk-type=pd-standard `
        --boot-disk-size=$($budget.bootDisk.sizeGb)GB `
        --boot-disk-auto-delete `
        --image-family=ubuntu-2204-lts `
        --image-project=ubuntu-os-cloud `
        --scopes=cloud-platform `
        --metadata="BUCKET=$Bucket,BUNDLE_OBJECT=$bundleName,RESULT_OBJECT=$resultName,LOG_OBJECT=$logName,FAILURE_OBJECT=$failureName,INSTANCE_NAME=$instance" `
        --metadata-from-file="startup-script=$startupPath"
    if ($LASTEXITCODE -ne 0) { throw "Phase-11 Spot instance creation failed; no retry is permitted." }
    $created = $true
    $start = Get-Date
    $submission.status = "running"
    $submission.instanceCreatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    $submission | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $submissionPath -Encoding UTF8

    $deadline = $start.AddSeconds([int]$budget.maxRunDurationSeconds)
    $finishUri = "gs://$Bucket/$finishName"
    $found = $false
    while ((Get-Date) -lt $deadline) {
        $listExit = 1
        try { & gcloud storage ls $finishUri *> $null; $listExit = $LASTEXITCODE } catch { $listExit = 1 }
        if ($listExit -eq 0) { $found = $true; break }
        Start-Sleep -Seconds 10
    }
    $resultRetrieved, $workerExitCode = $false, $null
    if ($found) {
        try {
            & gcloud storage cp "gs://$Bucket/$resultName" $resultPath
            if ($LASTEXITCODE -eq 0) {
                & tar.exe -xzf $resultPath -C (Join-Path $p11 "results")
                $resultRetrieved = ($LASTEXITCODE -eq 0)
            }
        } catch { $resultRetrieved = $false }
        try { & gcloud storage cp "gs://$Bucket/$logName" $workerLogPath } catch { }
        try { & gcloud storage cp $finishUri $finishPath } catch { }
        if (Test-Path -LiteralPath $finishPath) { $workerExitCode = (Get-Content -LiteralPath $finishPath -Raw | ConvertFrom-Json).exitCode }
        $submission.status = if ($workerExitCode -eq 0 -and $resultRetrieved) { "worker-finished" } else { "worker-failed-or-result-missing" }
    } else {
        $submission.status = "lifetime-timeout"
        try { & gcloud storage cp "gs://$Bucket/$failureName" $workerLogPath } catch { }
    }
} finally {
    if (-not $created -and $submission.status -eq "staging") { $submission.status = "launch-failed-before-instance" }
    if ($created) {
        & gcloud compute instances delete $instance --project=$Project --zone=$Zone --quiet
        $deleted = ($LASTEXITCODE -eq 0)
    }
    $elapsed = if ($start) { ((Get-Date) - $start).TotalSeconds } else { 0.0 }
    $submission.finishedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    $submission.elapsedSeconds = $elapsed
    $submission.instanceDeleteConfirmed = $deleted
    $submission.conservativeComputeEstimateUsd = [math]::Round(($elapsed/3600.0)*[double]$budget.conservativeComputeRateUsdPerHour, 5)
    $submission.estimatedNewAggregateUsd = [math]::Min([double]$budget.approvedRemainingUsd,
        $submission.conservativeComputeEstimateUsd + [double]$budget.storageNetworkArtifactReserveUsd + [double]$budget.contingencyUsd)
    $submission.temporaryGcsObjects = @($bundleName,$resultName,$logName,$failureName,$finishName)
    $submission | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $submissionPath -Encoding UTF8
    foreach ($object in @($bundleName,$resultName,$logName,$failureName,$finishName)) {
        try { & gcloud storage rm "gs://$Bucket/$object" --quiet *> $null } catch { }
    }
}

if ($submission.status -ne "worker-finished" -or -not $deleted) {
    throw "Phase-11 worker did not finish and confirm deletion; inspect the retained local worker log and receipt."
}
Write-Output ($submission | ConvertTo-Json -Depth 10)
