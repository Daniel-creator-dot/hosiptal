# PowerShell script to update Docker with Payer Type System changes
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Updating Docker with Payer Type System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/5] Stopping web service..." -ForegroundColor Yellow
docker-compose stop web

Write-Host ""
Write-Host "[2/5] Rebuilding web container..." -ForegroundColor Yellow
docker-compose build web

Write-Host ""
Write-Host "[3/5] Starting web service..." -ForegroundColor Yellow
docker-compose up -d web

Write-Host ""
Write-Host "[4/5] Waiting for service to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "[5/5] Verifying files..." -ForegroundColor Yellow
Write-Host ""

# Check if files exist
$files = @(
    "/app/hospital/services/visit_payer_sync_service.py",
    "/app/hospital/views_frontdesk_visit.py",
    "/app/hospital/signals_visit_payer_sync.py"
)

foreach ($file in $files) {
    $result = docker-compose exec -T web test -f $file 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $file exists" -ForegroundColor Green
    } else {
        Write-Host "✗ $file NOT FOUND" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Checking service status..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose ps web

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Testing signal import..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose exec -T web python manage.py shell -c "import hospital.signals_visit_payer_sync; print('✓ Signal module loaded')" 2>&1

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Update Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "If changes don't appear:" -ForegroundColor Yellow
Write-Host "1. Restart Docker Desktop" -ForegroundColor Yellow
Write-Host "2. Clear browser cache (Ctrl+Shift+R)" -ForegroundColor Yellow
Write-Host "3. Check Docker logs: docker-compose logs web" -ForegroundColor Yellow
Write-Host ""
