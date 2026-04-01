# Complete Django HMS Server Startup Script
# Starts PostgreSQL (via Docker) and Django server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Django HMS Complete Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location d:\chm

# Step 1: Check/Start Docker
Write-Host "Step 1: Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit
}
Write-Host "✓ Docker is running" -ForegroundColor Green

# Step 2: Start PostgreSQL via Docker
Write-Host ""
Write-Host "Step 2: Starting PostgreSQL database..." -ForegroundColor Yellow
docker-compose up -d db 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ PostgreSQL container started" -ForegroundColor Green
    Write-Host "Waiting for database to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # Wait for database to be ready
    $maxAttempts = 12
    $attempt = 0
    $dbReady = $false
    
    while ($attempt -lt $maxAttempts -and -not $dbReady) {
        $attempt++
        try {
            $result = python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings'); import django; django.setup(); from django.db import connection; connection.ensure_connection(); print('OK')" 2>&1
            if ($result -match "OK") {
                $dbReady = $true
                Write-Host "✓ Database is ready!" -ForegroundColor Green
            } else {
                Write-Host "  Attempt $attempt/$maxAttempts - Waiting..." -ForegroundColor Gray
                Start-Sleep -Seconds 2
            }
        } catch {
            Write-Host "  Attempt $attempt/$maxAttempts - Waiting..." -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    }
    
    if (-not $dbReady) {
        Write-Host "⚠ Database may not be fully ready, but continuing..." -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠ Could not start PostgreSQL container" -ForegroundColor Yellow
    Write-Host "Trying to continue anyway..." -ForegroundColor Yellow
}

# Step 3: Start Django Server
Write-Host ""
Write-Host "Step 3: Starting Django server..." -ForegroundColor Cyan
Write-Host "Server will be available at:" -ForegroundColor Green
Write-Host "  - http://localhost:8000" -ForegroundColor White
Write-Host "  - http://192.168.2.216:8000" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python manage.py runserver 0.0.0.0:8000
