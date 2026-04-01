# PowerShell script to restart Docker and Django
# This will stop containers, restart Docker, and start Django server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RESTARTING DOCKER AND DJANGO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
Set-Location D:\chm

# Step 1: Stop Docker containers
Write-Host "Step 1: Stopping Docker containers..." -ForegroundColor Yellow
docker-compose down

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Warning: docker-compose down failed (containers may not be running)" -ForegroundColor Yellow
}

Write-Host "✅ Containers stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Restart Docker Desktop (user needs to do this manually)
Write-Host "Step 2: Please restart Docker Desktop manually:" -ForegroundColor Yellow
Write-Host "  1. Open Docker Desktop" -ForegroundColor White
Write-Host "  2. Click 'Restart' or close and reopen Docker Desktop" -ForegroundColor White
Write-Host "  3. Wait for Docker to fully start (whale icon in system tray)" -ForegroundColor White
Write-Host ""
Write-Host "Press any key after Docker Desktop has restarted..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Write-Host ""

# Step 3: Start Docker containers
Write-Host "Step 3: Starting Docker containers..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Docker containers started" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to start Docker containers" -ForegroundColor Red
    Write-Host "Please check Docker Desktop is running and try again" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 4: Wait for database to be ready
Write-Host "Step 4: Waiting for database to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Step 5: Run migrations
Write-Host "Step 5: Running database migrations..." -ForegroundColor Yellow
python manage.py migrate --noinput

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Migrations completed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Some migrations may have failed" -ForegroundColor Yellow
}

Write-Host ""

# Step 6: Import JERRY.xlsx data
Write-Host "Step 6: Importing JERRY.xlsx data..." -ForegroundColor Yellow
python fix_and_import_jerry.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Import completed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Import may have failed" -ForegroundColor Yellow
}

Write-Host ""

# Step 7: Start Django server
Write-Host "Step 7: Starting Django development server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ READY! Starting Django server..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Server will be available at:" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  http://192.168.2.216:8000" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start Django server
python manage.py runserver 0.0.0.0:8000


