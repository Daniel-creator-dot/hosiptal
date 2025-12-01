# PowerShell script to update .env file for PostgreSQL Desktop
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Desktop Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item env.local.example .env
    Write-Host "Created .env file" -ForegroundColor Green
}

# Read current .env
$envContent = Get-Content .env -Raw

# Check if already configured for PostgreSQL
if ($envContent -match "DATABASE_URL=postgresql://") {
    Write-Host "PostgreSQL is already configured in .env" -ForegroundColor Green
    Write-Host ""
    Write-Host "Current DATABASE_URL:" -ForegroundColor Yellow
    $envContent | Select-String -Pattern "DATABASE_URL=.*" | ForEach-Object { Write-Host $_.Line -ForegroundColor White }
    Write-Host ""
    $update = Read-Host "Do you want to update it? (y/n)"
    if ($update -ne "y") {
        Write-Host "Exiting..." -ForegroundColor Yellow
        exit
    }
}

# Get PostgreSQL credentials
Write-Host ""
Write-Host "Enter PostgreSQL Desktop credentials:" -ForegroundColor Cyan
$username = Read-Host "Username (default: postgres)"
if ([string]::IsNullOrWhiteSpace($username)) {
    $username = "postgres"
}

$password = Read-Host "Password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

$database = Read-Host "Database name (default: hms_db)"
if ([string]::IsNullOrWhiteSpace($database)) {
    $database = "hms_db"
}

$port = Read-Host "Port (default: 5432)"
if ([string]::IsNullOrWhiteSpace($port)) {
    $port = "5432"
}

# Build DATABASE_URL
$databaseUrl = "postgresql://${username}:${passwordPlain}@host.docker.internal:${port}/${database}"

# Update .env file
Write-Host ""
Write-Host "Updating .env file..." -ForegroundColor Yellow

# Replace SQLite or old PostgreSQL URL
$envContent = $envContent -replace "DATABASE_URL=.*", "DATABASE_URL=$databaseUrl"

# If DATABASE_URL doesn't exist, add it
if ($envContent -notmatch "DATABASE_URL=") {
    $envContent += "`n# Database Configuration`nDATABASE_URL=$databaseUrl`n"
}

# Save updated .env
$envContent | Set-Content .env -NoNewline

Write-Host "✅ .env file updated!" -ForegroundColor Green
Write-Host ""
Write-Host "DATABASE_URL: $databaseUrl" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Make sure PostgreSQL Desktop is running"
Write-Host "2. Create database '$database' in pgAdmin"
Write-Host "3. Restart Docker: docker-compose restart web"
Write-Host "4. Test connection: docker-compose exec web python manage.py dbshell"
Write-Host ""















