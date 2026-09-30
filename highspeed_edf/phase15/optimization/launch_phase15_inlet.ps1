param(
    [string]$Bucket = "aero-governed-blockers-988177451335-20260919",
    [string]$Project = "",
    [string]$Zone = "us-central1-b",
    [double]$ApprovedBudgetUsd = 0.10,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$study = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$opt   = Join-Path $study "phase15\optimization"
$res   = Join-Path $study "phase15\results"

$ratePerHour  = 0.20
$maxLifetimeS = 1200
$computeMax   = [math]::Round($maxLifetimeS / 3600.0 * $ratePerHour, 5)
$storageNet   = 0.020
$contingency  = [math]::Round($ApprovedBudgetUsd - $computeMax - $storageNet, 5)
if (($computeMax + $storageNet) -gt $ApprovedBudgetUsd) { throw "Budget guard failed" }
Write-Host ("budget compute={0} storage={1} contingency={2} approved={3}" -f $computeMax, $storageNet, $contingency, $ApprovedBudgetUsd)

if (-not $Project) { $Project = (& gcloud config get-value project 2>$null).Trim() }
if (-not $Project) { throw "No active GCP project." }

$runId    = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$instance = "hsedf-p15-" + ($runId.ToLower().Replace("t","-").Replace("z",""))
$prefix   = "highspeed-edf-phase15-inlet-$runId"
$bundle   = "$prefix-input.tar.gz"
$result   = "$prefix-output.tar.gz"
$wlog     = "$prefix-worker.log"
$fail     = "$prefix-failure.log"
$finish   = "$prefix-finish.json"
$bundlePath = Join-Path $res "phase15_inlet_bundle.tar.gz"
$startupFile = Join-Path $opt "phase15_inlet_worker_startup.sh"

Push-Location $study
try {
    & tar.exe -czf $bundlePath phase15\optimization\phase15_inlet_worker.py
    if ($LASTEXITCODE -ne 0) { throw "bundle failed" }
} finally { Pop-Location }

& gcloud storage cp $bundlePath "gs://$Bucket/$bundle" --quiet
if ($LASTEXITCODE -ne 0) { throw "upload failed" }

if ($DryRun) {
    Write-Host "DRY RUN would create $instance in $Zone, budget $ApprovedBudgetUsd, lifetime ${maxLifetimeS}s"
    return
}

$metaPairs = @(
    "BUCKET=$Bucket",
    "BUNDLE_OBJECT=$bundle",
    "RESULT_OBJECT=$result",
    "LOG_OBJECT=$wlog",
    "FAILURE_OBJECT=$fail",
    "INSTANCE_NAME=$instance"
)
$metaArg  = "--metadata=" + ($metaPairs -join ",")
$startupArg = "--metadata-from-file=startup-script=" + $startupFile

$zones = @($Zone, "us-central1-a", "us-central1-c", "us-central1-f", "us-east1-b", "us-west1-b")
$machines = @("e2-standard-2", "e2-standard-4", "e2-medium")
$created = $false
foreach ($m in $machines) {
    foreach ($z in $zones) {
        $createArgs = @(
            "compute","instances","create",$instance,
            "--project=$Project","--zone=$z","--machine-type=$m",
            "--provisioning-model=SPOT","--instance-termination-action=DELETE",
            "--max-run-duration=${maxLifetimeS}s",
            "--boot-disk-size=20GB","--boot-disk-type=pd-standard",
            "--image-family=ubuntu-2204-lts","--image-project=ubuntu-os-cloud",
            "--scopes=storage-rw",
            $metaArg, $startupArg,
            "--quiet"
        )
        & gcloud @createArgs 2>$null
        if ($LASTEXITCODE -eq 0) { $created = $true; $Zone = $z; Write-Host "created $instance ($m) in $z"; break }
        Write-Host "retry: $m in $z unavailable"
    }
    if ($created) { break }
}
if (-not $created) { throw "instance create failed in every zone/machine tried" }
Write-Host "instance $instance created; waiting up to $maxLifetimeS s"

$deadline = (Get-Date).AddSeconds($maxLifetimeS + 180)
$found = $false
do {
    Start-Sleep -Seconds 20
    $obj = & gcloud storage ls "gs://$Bucket/$finish" 2>$null
    if ($obj) { $found = $true }
} while ((-not $found) -and ((Get-Date) -lt $deadline))

if ($found) {
    & gcloud storage cp "gs://$Bucket/$result" (Join-Path $res "phase15_inlet_cloud_output.tar.gz") --quiet
    & gcloud storage cp "gs://$Bucket/$wlog"   (Join-Path $res "phase15_inlet_worker.log") --quiet
    & gcloud storage cp "gs://$Bucket/$finish" (Join-Path $res "phase15_inlet_finish.json") --quiet
}
& gcloud compute instances delete $instance --project=$Project --zone=$Zone --quiet 2>$null
Write-Host ("done. results={0}" -f $found)

