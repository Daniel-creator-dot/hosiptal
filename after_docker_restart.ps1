# PowerShell script to run after Docker Desktop restart
# This will fix migrations and import JERRY.xlsx data

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "JERRY.XLSX IMPORT - AFTER DOCKER RESTART" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
Set-Location D:\chm

Write-Host "Step 1: Running fix and import script..." -ForegroundColor Yellow
python fix_and_import_jerry.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✅ IMPORT COMPLETED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Records should now appear in:" -ForegroundColor Cyan
    Write-Host "  - Insurance Receivable page" -ForegroundColor White
    Write-Host "  - Balance Sheet" -ForegroundColor White
    Write-Host "  - Accounts Payable Report" -ForegroundColor White
    Write-Host "  - General Ledger" -ForegroundColor White
    Write-Host "  - Trial Balance" -ForegroundColor White
    Write-Host "  - AR Aging Report" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "❌ IMPORT FAILED!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please check the error messages above." -ForegroundColor Yellow
    Write-Host "You can also try running manually:" -ForegroundColor Yellow
    Write-Host "  python manage.py import_jerry_excel" -ForegroundColor White
    Write-Host ""
}

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")


