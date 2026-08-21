# Registers a Windows Scheduled Task to sync local HMS database to live every N minutes.
# WARNING: Frequent sync can slow local HMS (heavy DB reads/writes). Prefer manual sync:
#   .\AUTO_SYNC_LOCAL_TO_LIVE.bat
# To disable automatic sync:
#   .\REMOVE_AUTO_SYNC_TO_LIVE.ps1
#
# Run once from an elevated PowerShell prompt:
#   Set-ExecutionPolicy -Scope Process Bypass; .\SETUP_AUTO_SYNC_TO_LIVE.ps1

param(
    [int]$IntervalMinutes = 15,
    [string]$TaskName = "HMS-LocalToLiveSync"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Batch = Join-Path $Root "AUTO_SYNC_LOCAL_TO_LIVE.bat"
$EnvSync = Join-Path $Root ".env.sync"
$EnvExample = Join-Path $Root "env.sync.example"

if (-not (Test-Path $EnvSync)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvSync
        Write-Host "Created .env.sync from env.sync.example - edit LIVE_DATABASE_URL before the task runs."
    } else {
        Write-Error ".env.sync not found. Create it with LIVE_DATABASE_URL before scheduling."
    }
}

if (-not (Test-Path $Batch)) {
    Write-Error "Missing AUTO_SYNC_LOCAL_TO_LIVE.bat in $Root"
}

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Batch`"" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Sync local HMS PostgreSQL to live Supabase every $IntervalMinutes minutes" -Force

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered."
Write-Host "  Runs every: $IntervalMinutes minutes"
Write-Host "  Script:     $Batch"
Write-Host "  Log file:   $Root\logs\local_to_live_sync.log"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit $EnvSync and set LIVE_DATABASE_URL"
Write-Host "  2. Test once:  python auto_sync_local_to_live.py --dry-run"
Write-Host "  3. Test sync:  .\AUTO_SYNC_LOCAL_TO_LIVE.bat"
Write-Host "  4. Task runs automatically in background"
Write-Host ""
Write-Host "To remove: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
