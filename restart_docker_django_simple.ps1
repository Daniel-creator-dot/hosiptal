# Simple script to restart Docker and Django
# Run this after manually restarting Docker Desktop

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RESTARTING DOCKER AND DJANGO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location D:\chm

# Step 1: Stop containers
Write-Host "Stopping Docker containers..." -ForegroundColor Yellow
docker-compose down 2>&1 | Out-Null
Write-Host "✅ Containers stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Wait a moment
Write-Host "Waiting 3 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Step 3: Start containers
Write-Host "Starting Docker containers..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Docker containers started" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to start containers. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: Wait for database
Write-Host "Waiting for database to be ready (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Step 5: Run migrations
Write-Host "Running migrations..." -ForegroundColor Yellow
python manage.py migrate --noinput
Write-Host "✅ Migrations completed" -ForegroundColor Green
Write-Host ""

# Step 6: Import JERRY.xlsx
Write-Host "Importing JERRY.xlsx data..." -ForegroundColor Yellow
python fix_and_import_jerry.py
Write-Host ""

# Step 7: Start Django
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Starting Django server..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Server will be at:" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  http://192.168.2.216:8000" -ForegroundColor White
Write-Host ""

python manage.py runserver 0.0.0.0:8000


