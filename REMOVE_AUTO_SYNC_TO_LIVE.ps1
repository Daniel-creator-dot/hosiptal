# Stops automatic local -> live sync (Windows Scheduled Task).
# Manual sync still works: .\AUTO_SYNC_LOCAL_TO_LIVE.bat

param(
    [string]$TaskName = "HMS-LocalToLiveSync"
)

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if (-not $task) {
    Write-Host "Scheduled task '$TaskName' is not registered. Nothing to remove."
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task '$TaskName'."
Write-Host ""
Write-Host "To sync manually, run:"
Write-Host "  .\AUTO_SYNC_LOCAL_TO_LIVE.bat"
Write-Host ""
Write-Host "To re-enable automatic sync (not recommended if it slows the system):"
Write-Host "  .\SETUP_AUTO_SYNC_TO_LIVE.ps1"
