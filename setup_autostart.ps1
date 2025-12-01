# PowerShell script to set up HMS auto-start on Windows boot
# Run this script as Administrator for best results

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "HMS Auto-Start Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = $PSScriptRoot
$startupScript = Join-Path $scriptPath "startup_hms.bat"
$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "HMS_AutoStart.lnk"

Write-Host "Setting up auto-start..." -ForegroundColor Yellow
Write-Host "Project path: $scriptPath" -ForegroundColor White
Write-Host "Startup folder: $startupFolder" -ForegroundColor White
Write-Host ""

# Method 1: Create shortcut in Startup folder
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = $startupScript
    $Shortcut.WorkingDirectory = $scriptPath
    $Shortcut.Description = "HMS Docker Services Auto-Start"
    $Shortcut.Save()
    
    Write-Host "✅ Created startup shortcut" -ForegroundColor Green
    Write-Host "   Location: $shortcutPath" -ForegroundColor White
} catch {
    Write-Host "⚠️  Could not create startup shortcut" -ForegroundColor Yellow
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""

# Method 2: Create scheduled task (more reliable)
$taskName = "HMS_Docker_AutoStart"
$taskDescription = "Automatically start HMS Docker services on system boot"

Write-Host "Creating scheduled task..." -ForegroundColor Yellow

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "   Removed existing task" -ForegroundColor White
}

# Create new task
$action = New-ScheduledTaskAction -Execute $startupScript -WorkingDirectory $scriptPath
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $taskDescription -Force | Out-Null
    Write-Host "✅ Created scheduled task" -ForegroundColor Green
    Write-Host "   Task name: $taskName" -ForegroundColor White
} catch {
    Write-Host "⚠️  Could not create scheduled task (may need Administrator)" -ForegroundColor Yellow
    Write-Host "   Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "To create manually:" -ForegroundColor Yellow
    Write-Host "   1. Open Task Scheduler" -ForegroundColor White
    Write-Host "   2. Create Basic Task" -ForegroundColor White
    Write-Host "   3. Trigger: When computer starts" -ForegroundColor White
    Write-Host "   4. Action: Start program" -ForegroundColor White
    Write-Host "   5. Program: $startupScript" -ForegroundColor White
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "HMS services will now start automatically on boot." -ForegroundColor White
Write-Host ""
Write-Host "To test:" -ForegroundColor Yellow
Write-Host "   1. Restart your computer" -ForegroundColor White
Write-Host "   2. Wait 1-2 minutes for Docker Desktop to start" -ForegroundColor White
Write-Host "   3. Check: docker-compose ps" -ForegroundColor White
Write-Host ""
Write-Host "To disable auto-start:" -ForegroundColor Yellow
Write-Host "   - Delete shortcut from Startup folder" -ForegroundColor White
Write-Host "   - Or disable task in Task Scheduler" -ForegroundColor White
Write-Host ""















