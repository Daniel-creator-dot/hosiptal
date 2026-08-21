# Pin HMS auto-start and Docker to C:\chm only (fixes legacy D:\chm shortcuts).
$CanonicalRoot = 'C:\chm'
$startupScript = Join-Path $CanonicalRoot 'startup_hms.bat'
$ensureScript = Join-Path $CanonicalRoot 'scripts\ensure_c_chm.ps1'

Write-Host '========================================' -ForegroundColor Cyan
Write-Host 'Maintain HMS on C:\chm' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

if (-not (Test-Path $CanonicalRoot)) {
    Write-Error "Canonical root not found: $CanonicalRoot"
    exit 1
}

Set-Location $CanonicalRoot

Write-Host '[1/4] Verifying Docker mount...' -ForegroundColor Yellow
& $ensureScript -Fix
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Failed to verify/fix Docker mount.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '[2/4] Updating Windows Startup shortcut...' -ForegroundColor Yellow
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder 'HMS_AutoStart.lnk'
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = $startupScript
    $Shortcut.WorkingDirectory = $CanonicalRoot
    $Shortcut.Description = 'HMS Docker Services Auto-Start (C:\chm)'
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()
    Write-Host "OK: $shortcutPath -> $startupScript" -ForegroundColor Green
} catch {
    Write-Host "Could not update startup shortcut: $_" -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '[3/4] Updating scheduled task HMS_Docker_AutoStart...' -ForegroundColor Yellow
$taskName = 'HMS_Docker_AutoStart'
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
$hmsAction = New-ScheduledTaskAction -Execute $startupScript -WorkingDirectory $CanonicalRoot
$hmsTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$hmsTrigger.Delay = 'PT2M'
$hmsPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$hmsSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
try {
    Register-ScheduledTask -TaskName $taskName -Action $hmsAction -Trigger $hmsTrigger -Principal $hmsPrincipal -Settings $hmsSettings -Description 'Start HMS from C:\chm after login' -Force | Out-Null
    Write-Host 'OK: Scheduled task points to C:\chm' -ForegroundColor Green
} catch {
    Write-Host "Skipped scheduled task (run SETUP_MAINTAIN_C_CHM.bat as Administrator to enable): $_" -ForegroundColor Yellow
}

Write-Host ''
Write-Host '[4/4] Summary' -ForegroundColor Yellow
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut($shortcutPath)
Write-Host "  Startup shortcut: $($lnk.TargetPath)" -ForegroundColor White
Write-Host "  Working folder:   $($lnk.WorkingDirectory)" -ForegroundColor White
Write-Host ''
Write-Host 'Done. HMS will always start from C:\chm.' -ForegroundColor Green
Write-Host 'Do not run docker compose from D:\chm.' -ForegroundColor DarkYellow
Write-Host ''
