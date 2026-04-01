# Fix PostgreSQL Authentication for HMS
# PowerShell version with better error handling

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Fix PostgreSQL Authentication" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Find PostgreSQL psql.exe
$psqlPath = $null
$postgresVersions = @(16, 15, 14, 13, 12)

foreach ($version in $postgresVersions) {
    $path = "C:\Program Files\PostgreSQL\$version\bin\psql.exe"
    if (Test-Path $path) {
        $psqlPath = $path
        Write-Host "Found PostgreSQL at: $psqlPath" -ForegroundColor Green
        break
    }
}

# Try PATH as fallback
if (-not $psqlPath) {
    $psqlInPath = Get-Command psql -ErrorAction SilentlyContinue
    if ($psqlInPath) {
        $psqlPath = $psqlInPath.Path
        Write-Host "Found PostgreSQL in PATH: $psqlPath" -ForegroundColor Green
    }
}

if (-not $psqlPath) {
    Write-Host "[ERROR] PostgreSQL psql command not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure PostgreSQL is installed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternative: Use pgAdmin GUI method:" -ForegroundColor Yellow
    Write-Host "  Run: FIX_POSTGRESQL_AUTH_SIMPLE.bat" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 1: Creating SQL script..." -ForegroundColor Cyan
Write-Host ""

# Create temporary SQL script
$tempSql = [System.IO.Path]::GetTempFileName() + ".sql"
$sqlContent = @"
-- Fix HMS PostgreSQL Authentication
-- Create user if not exists
DO `$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'hms_user') THEN
        CREATE USER hms_user WITH PASSWORD 'hms_password';
    ELSE
        ALTER USER hms_user WITH PASSWORD 'hms_password';
    END IF;
END
`$;

-- Create database if not exists
SELECT 'CREATE DATABASE hms_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hms_db')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;

-- Connect to hms_db and grant schema privileges
\c hms_db
GRANT ALL ON SCHEMA public TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;

-- Set user properties
\c postgres
ALTER ROLE hms_user SET client_encoding TO 'utf8';
ALTER ROLE hms_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE hms_user SET timezone TO 'UTC';
"@

$sqlContent | Out-File -FilePath $tempSql -Encoding UTF8

Write-Host "Step 2: Running PostgreSQL setup..." -ForegroundColor Cyan
Write-Host ""
Write-Host "You will be prompted for the PostgreSQL 'postgres' user password." -ForegroundColor Yellow
Write-Host "(This is the password you set during PostgreSQL installation)" -ForegroundColor Yellow
Write-Host ""

# Try to run psql
try {
    $process = Start-Process -FilePath $psqlPath -ArgumentList "-U", "postgres", "-f", $tempSql -Wait -NoNewWindow -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host "[SUCCESS] PostgreSQL Authentication Fixed!" -ForegroundColor Green
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Database Details:" -ForegroundColor Cyan
        Write-Host "  Host: localhost"
        Write-Host "  Port: 5432"
        Write-Host "  Database: hms_db"
        Write-Host "  User: hms_user"
        Write-Host "  Password: hms_password"
        Write-Host ""
        Write-Host "Your .env file should have:" -ForegroundColor Cyan
        Write-Host "  DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db"
        Write-Host ""
        Write-Host "Next Steps:" -ForegroundColor Cyan
        Write-Host "1. Verify .env file has correct DATABASE_URL"
        Write-Host "2. Run: python manage.py migrate"
        Write-Host "3. Start your Django server"
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[ERROR] Failed to connect to PostgreSQL!" -ForegroundColor Red
        Write-Host ""
        ShowErrorHelp
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] Failed to run PostgreSQL setup!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    ShowErrorHelp
} finally {
    # Clean up
    if (Test-Path $tempSql) {
        Remove-Item $tempSql -Force
    }
}

function ShowErrorHelp {
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "1. PostgreSQL service is not running" -ForegroundColor Yellow
    Write-Host "   - Check Services: services.msc" -ForegroundColor White
    Write-Host "   - Look for 'postgresql' service and start it" -ForegroundColor White
    Write-Host ""
    Write-Host "2. Wrong postgres password" -ForegroundColor Yellow
    Write-Host "   - Try the password you set during PostgreSQL installation" -ForegroundColor White
    Write-Host "   - Or check pgAdmin to see what password works" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Use pgAdmin GUI method instead:" -ForegroundColor Yellow
    Write-Host "   Run: FIX_POSTGRESQL_AUTH_SIMPLE.bat" -ForegroundColor White
    Write-Host ""
}

Read-Host "Press Enter to exit"



