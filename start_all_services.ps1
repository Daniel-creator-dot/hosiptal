# Django HMS Server Startup Script
# This script checks and starts all required services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Django HMS Server Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
Set-Location d:\chm

# Check PostgreSQL
Write-Host "Checking PostgreSQL..." -ForegroundColor Yellow
$pgService = Get-Service -Name "*postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($pgService) {
    if ($pgService.Status -ne 'Running') {
        Write-Host "Starting PostgreSQL service..." -ForegroundColor Yellow
        try {
            Start-Service -Name $pgService.Name -ErrorAction Stop
            Write-Host "✓ PostgreSQL started" -ForegroundColor Green
            Start-Sleep -Seconds 3
        } catch {
            Write-Host "✗ Failed to start PostgreSQL: $_" -ForegroundColor Red
            Write-Host "Please start PostgreSQL manually" -ForegroundColor Yellow
        }
    } else {
        Write-Host "✓ PostgreSQL is running" -ForegroundColor Green
    }
} else {
    Write-Host "⚠ PostgreSQL service not found" -ForegroundColor Yellow
    Write-Host "Checking if PostgreSQL is running as process..." -ForegroundColor Yellow
    $pgProcess = Get-Process -Name "postgres" -ErrorAction SilentlyContinue
    if ($pgProcess) {
        Write-Host "✓ PostgreSQL process found" -ForegroundColor Green
    } else {
        Write-Host "✗ PostgreSQL is not running!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please start PostgreSQL:" -ForegroundColor Yellow
        Write-Host "  1. Start PostgreSQL service: Start-Service postgresql-x64-XX" -ForegroundColor White
        Write-Host "  2. Or start Docker: docker-compose up -d" -ForegroundColor White
        Write-Host "  3. Or start PostgreSQL manually" -ForegroundColor White
        Write-Host ""
        $continue = Read-Host "Continue anyway? (y/n)"
        if ($continue -ne 'y') {
            exit
        }
    }
}

# Test database connection
Write-Host ""
Write-Host "Testing database connection..." -ForegroundColor Yellow
try {
    $result = python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings'); import django; django.setup(); from django.db import connection; connection.ensure_connection(); print('OK')" 2>&1
    if ($result -match "OK") {
        Write-Host "✓ Database connection successful" -ForegroundColor Green
    } else {
        Write-Host "✗ Database connection failed" -ForegroundColor Red
        Write-Host $result -ForegroundColor Red
        Write-Host ""
        Write-Host "Please check:" -ForegroundColor Yellow
        Write-Host "  1. PostgreSQL is running" -ForegroundColor White
        Write-Host "  2. Database credentials in .env file" -ForegroundColor White
        Write-Host "  3. Database 'hms_db' exists" -ForegroundColor White
        Write-Host ""
        $continue = Read-Host "Continue anyway? (y/n)"
        if ($continue -ne 'y') {
            exit
        }
    }
} catch {
    Write-Host "✗ Error testing database: $_" -ForegroundColor Red
}

# Start Django server
Write-Host ""
Write-Host "Starting Django server on 0.0.0.0:8000..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python manage.py runserver 0.0.0.0:8000
