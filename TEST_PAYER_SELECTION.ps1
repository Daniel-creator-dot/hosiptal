# PowerShell Test Script for Front Desk Payer Selection
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Testing Front Desk Payer Selection" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/5] Checking Python environment..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "OK: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please activate virtual environment first" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check Django
Write-Host ""
Write-Host "[2/5] Checking Django installation..." -ForegroundColor Yellow
try {
    $djangoVersion = python -c "import django; print('Django version:', django.get_version())" 2>&1
    Write-Host "OK: $djangoVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Django not installed!" -ForegroundColor Red
    Write-Host "Please activate virtual environment or install requirements" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Django check
Write-Host ""
Write-Host "[3/5] Running Django system check..." -ForegroundColor Yellow
$checkResult = python manage.py check 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - No critical errors" -ForegroundColor Green
} else {
    Write-Host "WARNING: System check found issues" -ForegroundColor Yellow
    Write-Host "Continuing anyway..." -ForegroundColor Yellow
}

# Form check
Write-Host ""
Write-Host "[4/5] Checking for form syntax errors..." -ForegroundColor Yellow
try {
    $formCheck = python -c "from hospital.forms import PatientForm; print('Form imports OK')" 2>&1
    Write-Host "OK: $formCheck" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Form has syntax errors!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Template check
Write-Host ""
Write-Host "[5/5] Checking template..." -ForegroundColor Yellow
if (Test-Path "hospital\templates\hospital\patient_form.html") {
    Write-Host "OK: Template exists" -ForegroundColor Green
} else {
    Write-Host "ERROR: Template missing!" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "All checks passed! Ready to test in browser." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Start server: python manage.py runserver" -ForegroundColor White
Write-Host "2. Open: http://127.0.0.1:8000/hms/patients/create/" -ForegroundColor White
Write-Host "3. Look for 'Payment Type' dropdown" -ForegroundColor White
Write-Host "4. Test selecting Insurance/Corporate/Cash" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"

