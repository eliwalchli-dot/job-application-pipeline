# setup_windows_scheduler.ps1
# Creates a Windows Task Scheduler job that runs fetch_apify.py daily at 5:45 AM.
# No admin rights needed (registers under current user).
#
# Usage:
#   .\scripts\setup_windows_scheduler.ps1           # create/update task
#   .\scripts\setup_windows_scheduler.ps1 -Remove   # delete the task
#   .\scripts\setup_windows_scheduler.ps1 -Test     # dry-run to verify

param(
    [switch]$Remove,
    [switch]$Test
)

$TaskName   = "JobPipeline-FetchApify"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptRoot = Split-Path -Parent $ScriptRoot
$ScriptPath = Join-Path $ScriptRoot "scripts\fetch_apify.py"
$PythonExe  = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    Write-Error "Python not found on PATH. Install Python 3.10+ and re-run."
    exit 1
}

if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Task '$TaskName' removed."
    } else {
        Write-Host "Task '$TaskName' not found - nothing to remove."
    }
    exit 0
}

if ($Test) {
    Write-Host "Running fetch_apify.py --dry-run to verify..."
    & $PythonExe $ScriptPath --dry-run
    exit $LASTEXITCODE
}

$Action  = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "05:45"
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs Apify LinkedIn job scraper daily at 5:45 AM; writes data/apify_latest.json for the 6 AM Cowork pipeline." `
    -Force | Out-Null

Write-Host ""
Write-Host "Task registered: '$TaskName'"
Write-Host "  Schedule : Daily at 05:45"
Write-Host "  Script   : $ScriptPath"
Write-Host "  Python   : $PythonExe"
Write-Host ""
Write-Host "IMPORTANT: Rotate your APIFY_TOKEN before the first real run."
Write-Host "  Get a new token at: https://console.apify.com/account#/integrations"
Write-Host "  Then update: Job Applications\pipeline_config.env"
Write-Host ""
Write-Host "To verify: .\scripts\setup_windows_scheduler.ps1 -Test"
