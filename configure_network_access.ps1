# PowerShell script to configure network access for HMS
# This updates docker-compose.yml with your current network IPs

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "HMS Network Access Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get all local network IPs
$networkIPs = Get-NetIPAddress -AddressFamily IPv4 | 
    Where-Object {
        ($_.IPAddress -like "192.168.*") -or 
        ($_.IPAddress -like "10.*") -or 
        ($_.IPAddress -like "172.16.*" -or $_.IPAddress -like "172.17.*" -or $_.IPAddress -like "172.18.*" -or $_.IPAddress -like "172.19.*" -or $_.IPAddress -like "172.20.*" -or $_.IPAddress -like "172.21.*" -or $_.IPAddress -like "172.22.*" -or $_.IPAddress -like "172.23.*" -or $_.IPAddress -like "172.24.*" -or $_.IPAddress -like "172.25.*" -or $_.IPAddress -like "172.26.*" -or $_.IPAddress -like "172.27.*" -or $_.IPAddress -like "172.28.*" -or $_.IPAddress -like "172.29.*" -or $_.IPAddress -like "172.30.*" -or $_.IPAddress -like "172.31.*")
    } | 
    Select-Object -ExpandProperty IPAddress

Write-Host "Detected network IPs:" -ForegroundColor Yellow
foreach ($ip in $networkIPs) {
    Write-Host "  - $ip" -ForegroundColor White
}
Write-Host ""

# Build ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS
$allowedHosts = "localhost,127.0.0.1,0.0.0.0," + ($networkIPs -join ",")
$csrfOriginsList = @("http://localhost:8000", "http://127.0.0.1:8000", "http://0.0.0.0:8000")
$networkIPs | ForEach-Object { $csrfOriginsList += "http://${_}:8000" }
$csrfOrigins = $csrfOriginsList -join ","

Write-Host "Updating docker-compose.yml..." -ForegroundColor Yellow

# Read docker-compose.yml
$composeContent = Get-Content docker-compose.yml -Raw

# Update ALLOWED_HOSTS
$composeContent = $composeContent -replace 'ALLOWED_HOSTS=.*', "ALLOWED_HOSTS=$allowedHosts"

# Update CSRF_TRUSTED_ORIGINS
$composeContent = $composeContent -replace 'CSRF_TRUSTED_ORIGINS=.*', "CSRF_TRUSTED_ORIGINS=$csrfOrigins"

# Write back
$composeContent | Set-Content docker-compose.yml -NoNewline

Write-Host "✅ Updated docker-compose.yml" -ForegroundColor Green
Write-Host ""

# Configure Windows Firewall
Write-Host "Configuring Windows Firewall..." -ForegroundColor Yellow

try {
    # Remove existing rule if it exists
    $existingRule = Get-NetFirewallRule -DisplayName "HMS Docker Port 8000" -ErrorAction SilentlyContinue
    if ($existingRule) {
        Remove-NetFirewallRule -DisplayName "HMS Docker Port 8000"
    }
    
    # Add new firewall rule
    New-NetFirewallRule -DisplayName "HMS Docker Port 8000" `
        -Direction Inbound `
        -LocalPort 8000 `
        -Protocol TCP `
        -Action Allow `
        -Description "Allow HMS application access on port 8000" | Out-Null
    
    Write-Host "✅ Windows Firewall configured" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not configure firewall (may need Administrator)" -ForegroundColor Yellow
    Write-Host "   Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "To configure manually:" -ForegroundColor Yellow
    Write-Host "   1. Open Windows Defender Firewall" -ForegroundColor White
    Write-Host "   2. Advanced Settings" -ForegroundColor White
    Write-Host "   3. Inbound Rules -> New Rule" -ForegroundColor White
    Write-Host "   4. Port -> TCP -> 8000 -> Allow" -ForegroundColor White
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Configuration Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your HMS application is now accessible at:" -ForegroundColor Yellow
foreach ($ip in $networkIPs) {
    Write-Host "   http://${ip}:8000" -ForegroundColor White
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. Restart Docker services: docker-compose restart web" -ForegroundColor White
Write-Host "   2. Test from another device on your network" -ForegroundColor White
Write-Host "   3. If using secondary router, ensure it's in bridge/AP mode" -ForegroundColor White
Write-Host ""

