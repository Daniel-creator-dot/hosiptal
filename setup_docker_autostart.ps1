# PowerShell script to configure Docker Desktop and HMS to start automatically
# Run this script to set up complete auto-start

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker Desktop Auto-Start Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = $PSScriptRoot
$startupScript = Join-Path $scriptPath "startup_hms.bat"

Write-Host "Step 1: Configuring Docker Desktop auto-start..." -ForegroundColor Yellow

# Method 1: Check Docker Desktop settings file
$dockerSettingsPath = "$env:APPDATA\Docker\settings.json"
if (Test-Path $dockerSettingsPath) {
    try {
        $dockerSettings = Get-Content $dockerSettingsPath -Raw | ConvertFrom-Json
        if (-not $dockerSettings.startOnStartup) {
            $dockerSettings | Add-Member -MemberType NoteProperty -Name "startOnStartup" -Value $true -Force
            $dockerSettings | ConvertTo-Json -Depth 10 | Set-Content $dockerSettingsPath
            Write-Host "✅ Docker Desktop auto-start enabled in settings" -ForegroundColor Green
        } else {
            Write-Host "✅ Docker Desktop auto-start already enabled" -ForegroundColor Green
        }
    } catch {
        Write-Host "⚠️  Could not update Docker settings file" -ForegroundColor Yellow
    }
}

# Method 2: Create scheduled task to start Docker Desktop
$dockerDesktopPath = Get-ChildItem "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
if (-not $dockerDesktopPath) {
    $dockerDesktopPath = Get-ChildItem "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
}

if ($dockerDesktopPath) {
    $taskName = "Docker_Desktop_AutoStart"
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    $action = New-ScheduledTaskAction -Execute $dockerDesktopPath.FullName
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    try {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Start Docker Desktop on system boot" -Force | Out-Null
        Write-Host "✅ Created scheduled task for Docker Desktop" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Could not create scheduled task (may need Administrator)" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Docker Desktop executable not found in standard locations" -ForegroundColor Yellow
    Write-Host "   Please enable auto-start manually in Docker Desktop settings" -ForegroundColor White
}

Write-Host ""

# Step 2: Update HMS startup script to wait for Docker
Write-Host "Step 2: Updating HMS startup script..." -ForegroundColor Yellow

$startupScriptContent = @"
@echo off
REM HMS Auto-Start Script
REM Waits for Docker Desktop and starts HMS services

REM Change to project directory
cd /d "%~dp0"

REM Wait for Docker Desktop to be ready (up to 2 minutes)
echo Waiting for Docker Desktop to start...
set MAX_WAIT=24
set WAIT_COUNT=0

:wait_docker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo Docker Desktop is ready!
    goto docker_ready
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% geq %MAX_WAIT% (
    echo ERROR: Docker Desktop did not start within 2 minutes
    echo Please start Docker Desktop manually
    exit /b 1
)
goto wait_docker

:docker_ready
echo Starting HMS services...
docker-compose up -d

REM Log the startup
echo HMS services started at %date% %time% >> startup_log.txt

"@

$startupScriptContent | Set-Content $startupScript -Encoding ASCII
Write-Host "✅ Updated startup script" -ForegroundColor Green
Write-Host ""

# Step 3: Ensure HMS startup task exists
Write-Host "Step 3: Configuring HMS auto-start..." -ForegroundColor Yellow

$hmsTaskName = "HMS_Docker_AutoStart"
$existingHmsTask = Get-ScheduledTask -TaskName $hmsTaskName -ErrorAction SilentlyContinue
if ($existingHmsTask) {
    Unregister-ScheduledTask -TaskName $hmsTaskName -Confirm:$false
}

$hmsAction = New-ScheduledTaskAction -Execute $startupScript -WorkingDirectory $scriptPath
$hmsTrigger = New-ScheduledTaskTrigger -AtStartup
$hmsPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$hmsSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

try {
    Register-ScheduledTask -TaskName $hmsTaskName -Action $hmsAction -Trigger $hmsTrigger -Principal $hmsPrincipal -Settings $hmsSettings -Description "Automatically start HMS Docker services on system boot" -Force | Out-Null
    Write-Host "✅ Created scheduled task for HMS services" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not create HMS scheduled task (may need Administrator)" -ForegroundColor Yellow
}

Write-Host ""

# Step 4: Configure Windows Startup folder as backup
Write-Host "Step 4: Creating Startup folder shortcut..." -ForegroundColor Yellow

$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "HMS_AutoStart.lnk"

try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = $startupScript
    $Shortcut.WorkingDirectory = $scriptPath
    $Shortcut.Description = "HMS Docker Services Auto-Start"
    $Shortcut.WindowStyle = 1  # Minimized
    $Shortcut.Save()
    Write-Host "✅ Created startup shortcut" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not create startup shortcut" -ForegroundColor Yellow
}

Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Docker Desktop will start automatically on boot" -ForegroundColor Green
Write-Host "✅ HMS services will start automatically after Docker Desktop" -ForegroundColor Green
Write-Host ""
Write-Host "To test:" -ForegroundColor Yellow
Write-Host "   1. Restart your computer" -ForegroundColor White
Write-Host "   2. Wait 2-3 minutes for everything to start" -ForegroundColor White
Write-Host "   3. Check: docker-compose ps" -ForegroundColor White
Write-Host "   4. Access: http://192.168.0.102:8000" -ForegroundColor White
Write-Host ""
Write-Host "To disable auto-start:" -ForegroundColor Yellow
Write-Host "   - Docker Desktop: Settings -> General -> Uncheck 'Start on login'" -ForegroundColor White
Write-Host "   - HMS: Task Scheduler -> Disable 'HMS_Docker_AutoStart'" -ForegroundColor White
Write-Host ""














