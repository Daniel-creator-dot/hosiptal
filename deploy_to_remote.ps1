# PowerShell script to deploy Drug Accountability System to remote server
# Run this from your local Windows machine

param(
    [string]$Server = "user@192.168.2.216",
    [string]$RemotePath = "/app/hospital",
    [string]$RemoteProjectPath = "/app"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying Drug Accountability System" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Files to deploy
$files = @(
    @{Local="hospital/urls.py"; Remote="$RemotePath/urls.py"},
    @{Local="hospital/views_drug_accountability.py"; Remote="$RemotePath/views_drug_accountability.py"},
    @{Local="hospital/views_departments.py"; Remote="$RemotePath/views_departments.py"},
    @{Local="hospital/models_drug_accountability.py"; Remote="$RemotePath/models_drug_accountability.py"},
    @{Local="hospital/migrations/1058_add_drug_accountability_system.py"; Remote="$RemotePath/migrations/1058_add_drug_accountability_system.py"},
    @{Local="hospital/templates/hospital/pharmacy_dashboard_worldclass.html"; Remote="$RemotePath/templates/hospital/pharmacy_dashboard_worldclass.html"}
)

Write-Host "Step 1: Copying files to remote server..." -ForegroundColor Yellow

foreach ($file in $files) {
    if (Test-Path $file.Local) {
        Write-Host "  Copying: $($file.Local) -> $($file.Remote)" -ForegroundColor Green
        scp $file.Local "${Server}:$($file.Remote)"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✓ Success" -ForegroundColor Green
        } else {
            Write-Host "    ✗ Failed" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "  ✗ File not found: $($file.Local)" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Step 2: Running migration on remote server..." -ForegroundColor Yellow

# Create migration script on remote server
$migrationScript = @"
#!/bin/bash
cd $RemoteProjectPath
python manage.py migrate hospital 1058_add_drug_accountability_system
"@

# Write script to temp file
$tempScript = [System.IO.Path]::GetTempFileName()
$migrationScript | Out-File -FilePath $tempScript -Encoding ASCII

# Copy and execute
Write-Host "  Executing migration..." -ForegroundColor Green
scp $tempScript "${Server}:/tmp/run_migration.sh"
ssh $Server "chmod +x /tmp/run_migration.sh && /tmp/run_migration.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host "    ✓ Migration completed" -ForegroundColor Green
} else {
    Write-Host "    ⚠ Migration may have failed - check output above" -ForegroundColor Yellow
}

# Cleanup
Remove-Item $tempScript -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart Django server on remote machine:" -ForegroundColor White
Write-Host "   ssh $Server" -ForegroundColor Gray
Write-Host "   cd $RemoteProjectPath" -ForegroundColor Gray
Write-Host "   python manage.py runserver 0.0.0.0:8000" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Test the URL:" -ForegroundColor White
Write-Host "   http://192.168.2.216:8000/hms/drug-returns/" -ForegroundColor Gray
Write-Host ""







