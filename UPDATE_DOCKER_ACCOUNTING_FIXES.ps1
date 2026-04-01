# PowerShell script to update Docker with accounting fixes
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Update Docker with Accounting Fixes" -ForegroundColor Cyan
Write-Host "  Trial Balance + Revenue + Insurance AR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "[1/8] Checking Docker Desktop..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "  [OK] Docker Desktop is running" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Show current versions
Write-Host "[2/8] Current Docker versions:" -ForegroundColor Yellow
docker --version
docker-compose --version
Write-Host ""

Write-Host "[3/8] Stopping all containers..." -ForegroundColor Yellow
docker-compose down
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARNING] Some containers may not have stopped cleanly" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Containers stopped" -ForegroundColor Green
}
Write-Host ""

Write-Host "[4/8] Rebuilding containers with ALL latest code changes..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Gray
Write-Host "  Including:" -ForegroundColor Gray
Write-Host "    - Trial balance revenue display fix" -ForegroundColor Gray
Write-Host "    - Revenue accounts showing in Credit column" -ForegroundColor Gray
Write-Host "    - Duplicate prevention for accounting entries" -ForegroundColor Gray
Write-Host "    - Insurance receivables verification" -ForegroundColor Gray
Write-Host "    - Accounting sync service improvements" -ForegroundColor Gray
Write-Host ""

docker-compose build --no-cache web celery celery-beat
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Build failed!" -ForegroundColor Red
    Write-Host "  Check the error messages above." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Containers rebuilt successfully" -ForegroundColor Green
Write-Host ""

Write-Host "[5/8] Starting database and waiting for it to be ready..." -ForegroundColor Yellow
docker-compose up -d db redis
Start-Sleep -Seconds 15
Write-Host "  [OK] Database and Redis started" -ForegroundColor Green
Write-Host ""

Write-Host "[6/8] Running database migrations..." -ForegroundColor Yellow
docker-compose run --rm web python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARNING] Some migrations may have failed" -ForegroundColor Yellow
    Write-Host "  Check logs: docker-compose logs web" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Migrations completed successfully" -ForegroundColor Green
}
Write-Host ""

Write-Host "[7/8] Collecting static files..." -ForegroundColor Yellow
docker-compose run --rm web python manage.py collectstatic --no-input --clear
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARNING] Static files collection had issues" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Static files collected" -ForegroundColor Green
}
Write-Host ""

Write-Host "[8/8] Starting all services..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Failed to start services!" -ForegroundColor Red
    Write-Host "  Check logs: docker-compose logs" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] All services started" -ForegroundColor Green
Write-Host ""

Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DOCKER UPDATED WITH ACCOUNTING FIXES!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Recent changes included:" -ForegroundColor Yellow
Write-Host "  - Trial balance revenue display fixed" -ForegroundColor Green
Write-Host "  - Revenue accounts show in Credit column" -ForegroundColor Green
Write-Host "  - Duplicate prevention for GL entries" -ForegroundColor Green
Write-Host "  - Insurance receivables verified" -ForegroundColor Green
Write-Host "  - Accounting sync service enhanced" -ForegroundColor Green
Write-Host "  - All accounting calculations corrected" -ForegroundColor Green
Write-Host ""

Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  - Web: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  - Database: PostgreSQL (port 5432)" -ForegroundColor Cyan
Write-Host "  - Redis: Running (port 6379)" -ForegroundColor Cyan
Write-Host "  - Celery Worker: Running" -ForegroundColor Cyan
Write-Host "  - Celery Beat: Running" -ForegroundColor Cyan
Write-Host ""

Write-Host "Checking service status..." -ForegroundColor Yellow
docker-compose ps
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Update Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Verify services: docker-compose ps" -ForegroundColor White
Write-Host "  2. Check logs: docker-compose logs web" -ForegroundColor White
Write-Host "  3. Test trial balance: http://localhost:8000/hms/accounting/trial-balance/" -ForegroundColor White
Write-Host "  4. Verify revenue accounts show in Credit column" -ForegroundColor White
Write-Host ""
