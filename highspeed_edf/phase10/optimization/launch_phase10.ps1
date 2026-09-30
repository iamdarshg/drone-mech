param(
    [string]$Bucket = "aero-governed-blockers-988177451335-20260919",
    [string]$Project = "",
    [string]$Zone = "us-central1-b"
)

$ErrorActionPreference = "Stop"
$study = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$phase10 = Join-Path $study "phase10"
$cfgPath = Join-Path $phase10 "configs\phase10_openfoam_study.json"
$startupPath = Join-Path $phase10 "optimization\phase10_worker_startup.sh"
$workerPath = Join-Path $phase10 "optimization\phase10_openfoam_worker.py"
$cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json
$budget = $cfg.executionBudget

if ([double]$budget.approvalCapUsd -gt 0.20 -or [double]$budget.estimatedMaximumAggregateUsd -gt 0.20) {
    throw "Phase-10 aggregate estimate exceeds the approved $0.20 limit."
}
if ([int]$budget.instanceCountMax -gt 5 -or [int]$budget.concurrentInstancesMax -ne 1 -or [int]$budget.maxRunDurationSeconds -gt 2700 -or $budget.terminationAction -ne "DELETE") {
    throw "Phase-10 worker lifetime/count/delete guard does not match the approved cap."
}
if (-not $Project) {
    $Project = (& gcloud config get-value project 2>$null).Trim()
}
if (-not $Project) { throw "No active GCP project is configured." }

$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$instance = "hsedf-p10-$($runId.ToLower().Replace('t','-').Replace('z',''))"
$prefix = "highspeed-edf-phase10-$runId"
$bundleName = "$prefix-input.tar.gz"
$resultName = "$prefix-output.tar.gz"
$logName = "$prefix-worker.log"
$failureName = "$prefix-failure.log"
$finishName = "$prefix-output-finish.json"
$bundlePath = Join-Path $phase10 "results\phase10_bundle.tar.gz"
$resultPath = Join-Path $phase10 "results\phase10_cloud_output.tar.gz"
$logPath = Join-Path $phase10 "results\phase10_worker.log"
$finishPath = Join-Path $phase10 "results\phase10_finish.json"
$runRecordPath = Join-Path $phase10 "results\phase10_submission.json"

Push-Location $study
try {
    & tar.exe -czf $bundlePath phase10\configs\phase10_openfoam_study.json phase10\templates\openfoam phase10\cases phase10\optimization\phase10_openfoam_worker.py
    if ($LASTEXITCODE -ne 0) { throw "Failed to package phase-10 cases." }
} finally {
    Pop-Location
}

$localPlan = [ordered]@{
    phase = 10
    status = "launching"
    runId = $runId
    project = $Project
    bucket = $Bucket
    instance = $instance
    zone = $Zone
    machineType = $budget.machineType
    provisioningModel = $budget.provisioningModel
    maximumLifetimeSeconds = [int]$budget.maxRunDurationSeconds
    terminationAction = $budget.terminationAction
    aggregateCapUsd = [double]$budget.approvalCapUsd
    computeCapUsd = [double]$budget.computeCapUsd
    otherAllowanceUsd = [double]$budget.storageNetworkAndLogsReserveUsd
    contingencyUsd = [double]$budget.contingencyReserveUsd
    cases = @($cfg.caseMatrix | ForEach-Object { $_.caseId })
    launchedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
}
$localPlan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $runRecordPath -Encoding UTF8

$created = $false
$deleted = $false
$start = $null
try {
    & gcloud storage cp $bundlePath "gs://$Bucket/$bundleName"
    if ($LASTEXITCODE -ne 0) { throw "Could not stage phase-10 inputs in the existing evidence bucket." }

    & gcloud compute instances create $instance `
        --project=$Project `
        --zone=$Zone `
        --machine-type=$($budget.machineType) `
        --provisioning-model=SPOT `
        --instance-termination-action=DELETE `
        --max-run-duration=$($budget.maxRunDurationSeconds)s `
        --boot-disk-type=pd-standard `
        --boot-disk-size=12GB `
        --boot-disk-auto-delete `
        --image-family=ubuntu-2204-lts `
        --image-project=ubuntu-os-cloud `
        --scopes=cloud-platform `
        --metadata="BUCKET=$Bucket,BUNDLE_OBJECT=$bundleName,RESULT_OBJECT=$resultName,LOG_OBJECT=$logName,FAILURE_OBJECT=$failureName,INSTANCE_NAME=$instance" `
        --metadata-from-file="startup-script=$startupPath"
    if ($LASTEXITCODE -ne 0) { throw "GCE Spot instance creation failed; no retry or alternate VM will be submitted." }
    $created = $true
    $start = Get-Date
    $localPlan.status = "running"
    $localPlan.instanceCreatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    $localPlan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $runRecordPath -Encoding UTF8

    $deadline = $start.AddSeconds([int]$budget.maxRunDurationSeconds)
    $finishUri = "gs://$Bucket/$finishName"
    $found = $false
    $resultRetrieved = $false
    $workerExitCode = $null
    while ((Get-Date) -lt $deadline) {
        $listExit = 1
        try {
            & gcloud storage ls $finishUri *> $null
            $listExit = $LASTEXITCODE
        } catch {
            $listExit = 1
        }
        if ($listExit -eq 0) { $found = $true; break }
        Start-Sleep -Seconds 15
    }

    if ($found) {
        try {
            & gcloud storage cp "gs://$Bucket/$resultName" $resultPath
            if ($LASTEXITCODE -eq 0) {
                & tar.exe -xzf $resultPath -C (Join-Path $phase10 "results")
                $resultRetrieved = ($LASTEXITCODE -eq 0)
            }
        } catch { $resultRetrieved = $false }
        try { & gcloud storage cp "gs://$Bucket/$logName" $logPath } catch { }
        try { & gcloud storage cp $finishUri $finishPath } catch { }
        if (Test-Path -LiteralPath $finishPath) {
            $workerExitCode = (Get-Content -LiteralPath $finishPath -Raw | ConvertFrom-Json).exitCode
        }
        $localPlan.status = if ($workerExitCode -eq 0 -and $resultRetrieved) { "worker-finished" } else { "worker-failed-or-result-missing" }
    } else {
        $localPlan.status = "local-poll-time-cap"
        & gcloud storage cp "gs://$Bucket/$failureName" $logPath
    }
} finally {
    if (-not $created -and $localPlan.status -eq "launching") {
        $localPlan.status = "launch-failed-before-instance"
    }
    if ($created) {
        & gcloud compute instances delete $instance --project=$Project --zone=$Zone --quiet
        $deleted = ($LASTEXITCODE -eq 0)
    }
    $elapsed = if ($start) { ((Get-Date) - $start).TotalSeconds } else { 0.0 }
    $localPlan.finishedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    $localPlan.elapsedSeconds = $elapsed
    $localPlan.vmDeleteRequestedAndConfirmed = $deleted
    $localPlan.conservativeComputeEstimateUsd = [math]::Round(($elapsed / 3600.0) * [double]$budget.conservativeComputeRateUsdPerHour, 5)
    $localPlan.priorFailedWorkerComputeEstimateUsd = [double]$budget.priorFailedWorkerComputeEstimateUsd
    $localPlan.aggregateComputeEstimateUsd = [math]::Round($localPlan.conservativeComputeEstimateUsd + $localPlan.priorFailedWorkerComputeEstimateUsd, 5)
    $localPlan.estimatedAggregateUsdCapped = [math]::Min([double]$budget.approvalCapUsd, $localPlan.aggregateComputeEstimateUsd + [double]$budget.storageNetworkAndLogsReserveUsd + [double]$budget.contingencyReserveUsd)
    $localPlan.actualBillingAmountUsd = $null
    $localPlan.gcsTemporaryObjects = @($bundleName, $resultName, $logName, $failureName, $finishName)
    $localPlan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $runRecordPath -Encoding UTF8
    foreach ($object in @($bundleName, $resultName, $logName, $failureName, $finishName)) {
        try { & gcloud storage rm "gs://$Bucket/$object" --quiet *> $null } catch { }
    }
}

if ($localPlan.status -ne "worker-finished" -or -not $deleted) {
    throw "Phase-10 worker did not finish and confirm instance deletion. Inspect phase10/results/phase10_submission.json and retained logs."
}
Write-Output ($localPlan | ConvertTo-Json -Depth 10)
