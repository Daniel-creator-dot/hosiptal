# PowerShell script to set up PostgreSQL database
# This will attempt to create the database using psql if available

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Database Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if psql is available
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    Write-Host "psql not found in PATH. Checking common locations..." -ForegroundColor Yellow
    
    $commonPaths = @(
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\14\bin\psql.exe",
        "C:\Program Files\PostgreSQL\13\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            $psqlPath = $path
            Write-Host "Found psql at: $path" -ForegroundColor Green
            break
        }
    }
    
    if (-not $psqlPath) {
        Write-Host "ERROR: psql not found. Please install PostgreSQL or add it to PATH." -ForegroundColor Red
        Write-Host ""
        Write-Host "You can manually create the database in pgAdmin:" -ForegroundColor Yellow
        Write-Host "1. Open pgAdmin" -ForegroundColor White
        Write-Host "2. Connect to your PostgreSQL server" -ForegroundColor White
        Write-Host "3. Right-click 'Databases' -> Create -> Database" -ForegroundColor White
        Write-Host "4. Name: hms_db" -ForegroundColor White
        Write-Host "5. Owner: postgres" -ForegroundColor White
        Write-Host "6. Click Save" -ForegroundColor White
        exit 1
    }
} else {
    $psqlPath = $psqlPath.Path
}

Write-Host "Using psql: $psqlPath" -ForegroundColor Green
Write-Host ""

# Database configuration
$dbName = "hms_db"
$dbUser = "postgres"
$dbPassword = "PASSWORD"
$dbHost = "localhost"
$dbPort = "5432"

Write-Host "Attempting to create database: $dbName" -ForegroundColor Cyan
Write-Host "User: $dbUser" -ForegroundColor White
Write-Host "Host: ${dbHost}:${dbPort}" -ForegroundColor White
Write-Host ""

# Set PGPASSWORD environment variable
$env:PGPASSWORD = $dbPassword

# Try to create database
$createDbCommand = "SELECT 1 FROM pg_database WHERE datname = '$dbName'"
$checkResult = & $psqlPath -h $dbHost -p $dbPort -U $dbUser -d postgres -t -c $createDbCommand 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not connect to PostgreSQL" -ForegroundColor Red
    Write-Host "Error: $checkResult" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please verify:" -ForegroundColor Yellow
    Write-Host "1. PostgreSQL Desktop is running" -ForegroundColor White
    Write-Host "2. Password is correct: $dbPassword" -ForegroundColor White
    Write-Host "3. PostgreSQL is listening on port $dbPort" -ForegroundColor White
    exit 1
}

# Check if database exists
$dbExists = $checkResult.Trim()
if ($dbExists -eq "1") {
    Write-Host "Database '$dbName' already exists!" -ForegroundColor Green
} else {
    Write-Host "Creating database '$dbName'..." -ForegroundColor Yellow
    $createResult = & $psqlPath -h $dbHost -p $dbPort -U $dbUser -d postgres -c "CREATE DATABASE $dbName OWNER $dbUser;" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database '$dbName' created successfully!" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to create database" -ForegroundColor Red
        Write-Host "Error: $createResult" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next step: Test connection from Docker" -ForegroundColor Yellow
Write-Host "Run: docker-compose exec web python manage.py migrate" -ForegroundColor White
Write-Host ""

