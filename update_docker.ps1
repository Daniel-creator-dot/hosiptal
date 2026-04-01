# Docker Desktop Update Script for Windows
# Run this script as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Docker Desktop Update Checker" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsPrincipal]::GetCurrent().Groups -contains [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544"))

if (-not $isAdmin) {
    Write-Host "⚠️  This script requires Administrator privileges!" -ForegroundColor Yellow
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Check current Docker version
Write-Host "Checking current Docker version..." -ForegroundColor Green
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "Current: $dockerVersion" -ForegroundColor White
} catch {
    Write-Host "❌ Docker is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Checking for updates using winget..." -ForegroundColor Green

# Check if winget is available
try {
    $wingetVersion = winget --version 2>&1
    Write-Host "✅ winget is available" -ForegroundColor Green
} catch {
    Write-Host "❌ winget is not available. Please use Method 1 (Docker Desktop Settings) instead." -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Check for Docker Desktop updates
Write-Host ""
Write-Host "Checking for Docker Desktop updates..." -ForegroundColor Green
$updateCheck = winget upgrade Docker.DockerDesktop --include-unknown 2>&1

if ($updateCheck -match "No applicable updates found" -or $updateCheck -match "No upgrades available") {
    Write-Host "✅ Docker Desktop is up to date!" -ForegroundColor Green
} else {
    Write-Host "📦 Update available!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Would you like to update now? (Y/N)" -ForegroundColor Cyan
    $response = Read-Host
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host ""
        Write-Host "Updating Docker Desktop..." -ForegroundColor Green
        Write-Host "⚠️  This may take a few minutes. Please wait..." -ForegroundColor Yellow
        Write-Host ""
        
        # Stop Docker Desktop if running
        Write-Host "Stopping Docker Desktop..." -ForegroundColor Yellow
        Stop-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        
        # Run winget upgrade
        winget upgrade Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
        
        Write-Host ""
        Write-Host "✅ Update complete!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Please restart Docker Desktop manually." -ForegroundColor Yellow
    } else {
        Write-Host "Update cancelled." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Update Check Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")








