# PowerShell script to start HMS server with network access
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting HMS Server - Network Access" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  WARNING: Not running as Administrator" -ForegroundColor Yellow
    Write-Host "Firewall configuration requires admin rights." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To configure firewall, run this script as Administrator:" -ForegroundColor Yellow
    Write-Host "  Right-click -> Run with PowerShell -> Run as Administrator" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Continuing to start server anyway..." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "✅ Running as Administrator" -ForegroundColor Green
    Write-Host ""
    
    # Configure firewall
    Write-Host "Configuring Windows Firewall for port 8000..." -ForegroundColor Cyan
    try {
        # Delete existing rule if it exists
        netsh advfirewall firewall delete rule name="HMS Port 8000" 2>$null
        
        # Add new rule
        $result = netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Firewall rule added successfully!" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Failed to add firewall rule" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Error configuring firewall: $_" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Check if port 8000 is in use
Write-Host "Checking if port 8000 is available..." -ForegroundColor Cyan
$portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "⚠️  WARNING: Port 8000 is already in use!" -ForegroundColor Yellow
    Write-Host "Please stop the existing server first." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to continue anyway, or Ctrl+C to cancel..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Write-Host ""
}

# Get current directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Display network IPs
Write-Host "Your network IP addresses:" -ForegroundColor Cyan
$ipAddresses = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -ExpandProperty IPAddress
foreach ($ip in $ipAddresses) {
    Write-Host "  - http://$ip`:8000" -ForegroundColor Green
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Django Development Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server will be accessible at:" -ForegroundColor Yellow
Write-Host "  - Local: http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  - Local: http://localhost:8000" -ForegroundColor White
foreach ($ip in $ipAddresses) {
    Write-Host "  - Network: http://$ip`:8000" -ForegroundColor White
}
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start the server
try {
    python manage.py runserver 0.0.0.0:8000
} catch {
    Write-Host ""
    Write-Host "❌ ERROR: Server failed to start!" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  1. Port 8000 already in use" -ForegroundColor White
    Write-Host "  2. Database connection failed" -ForegroundColor White
    Write-Host "  3. Missing Python dependencies" -ForegroundColor White
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}






