# PowerShell script to detect Docker Desktop host IP and local network IP
# This helps configure Docker for network access

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker IP Detection Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker Desktop is running
Write-Host "Checking Docker Desktop..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✅ Docker Desktop is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "   Please start Docker Desktop first" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}
Write-Host ""

# Detect Docker Desktop host IP (host.docker.internal)
Write-Host "Docker Desktop Host IP:" -ForegroundColor Yellow
Write-Host "   host.docker.internal (use this in DATABASE_URL)" -ForegroundColor White
Write-Host ""

# Detect local network IPs
Write-Host "Detecting local network IPs..." -ForegroundColor Yellow
$networkIPs = Get-NetIPAddress -AddressFamily IPv4 | 
    Where-Object {
        ($_.IPAddress -notlike "127.*") -and 
        ($_.IPAddress -notlike "169.254.*") -and
        (
            ($_.IPAddress -like "192.168.*") -or 
            ($_.IPAddress -like "10.*") -or 
            ($_.IPAddress -like "172.16.*") -or 
            ($_.IPAddress -like "172.17.*") -or 
            ($_.IPAddress -like "172.18.*") -or 
            ($_.IPAddress -like "172.19.*") -or 
            ($_.IPAddress -like "172.20.*") -or 
            ($_.IPAddress -like "172.21.*") -or 
            ($_.IPAddress -like "172.22.*") -or 
            ($_.IPAddress -like "172.23.*") -or 
            ($_.IPAddress -like "172.24.*") -or 
            ($_.IPAddress -like "172.25.*") -or 
            ($_.IPAddress -like "172.26.*") -or 
            ($_.IPAddress -like "172.27.*") -or 
            ($_.IPAddress -like "172.28.*") -or 
            ($_.IPAddress -like "172.29.*") -or 
            ($_.IPAddress -like "172.30.*") -or 
            ($_.IPAddress -like "172.31.*")
        )
    } | 
    Select-Object -ExpandProperty IPAddress

if ($networkIPs.Count -eq 0) {
    Write-Host "⚠️  No network IPs detected!" -ForegroundColor Yellow
    Write-Host "   This might mean:" -ForegroundColor White
    Write-Host "   - You're not connected to a network" -ForegroundColor White
    Write-Host "   - Your network uses a different IP range" -ForegroundColor White
    Write-Host ""
    Write-Host "   You can manually set your IP in docker-compose.yml" -ForegroundColor Yellow
} else {
    Write-Host "✅ Detected network IPs:" -ForegroundColor Green
    foreach ($ip in $networkIPs) {
        Write-Host "   - $ip" -ForegroundColor White
    }
    Write-Host ""
    
    # Ask if user wants to update docker-compose.yml
    Write-Host "Do you want to update docker-compose.yml with these IPs? (Y/N)" -ForegroundColor Cyan
    $response = Read-Host
    
    if ($response -eq "Y" -or $response -eq "y") {
        Write-Host ""
        Write-Host "Updating docker-compose.yml..." -ForegroundColor Yellow
        
        # Build ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS
        $allowedHosts = "localhost,127.0.0.1,0.0.0.0," + ($networkIPs -join ",")
        $csrfOriginsList = @("http://localhost:8000", "http://127.0.0.1:8000", "http://0.0.0.0:8000")
        $networkIPs | ForEach-Object { $csrfOriginsList += "http://${_}:8000" }
        $csrfOrigins = $csrfOriginsList -join ","
        
        # Read docker-compose.yml
        if (Test-Path "docker-compose.yml") {
            $composeContent = Get-Content docker-compose.yml -Raw
            
            # Update ALLOWED_HOSTS
            $composeContent = $composeContent -replace 'ALLOWED_HOSTS=.*', "ALLOWED_HOSTS=$allowedHosts"
            
            # Update CSRF_TRUSTED_ORIGINS
            $composeContent = $composeContent -replace 'CSRF_TRUSTED_ORIGINS=.*', "CSRF_TRUSTED_ORIGINS=$csrfOrigins"
            
            # Write back
            $composeContent | Set-Content docker-compose.yml -NoNewline
            
            Write-Host "✅ Updated docker-compose.yml" -ForegroundColor Green
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Cyan
            Write-Host "   1. Restart Docker services: docker-compose restart web" -ForegroundColor White
            Write-Host "   2. Access your app at:" -ForegroundColor White
            foreach ($ip in $networkIPs) {
                Write-Host "      http://${ip}:8000" -ForegroundColor White
            }
        } else {
            Write-Host "❌ docker-compose.yml not found!" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Docker Desktop Host IP:" -ForegroundColor Yellow
Write-Host "   Use: host.docker.internal" -ForegroundColor White
Write-Host "   Example DATABASE_URL: postgresql://user:pass@host.docker.internal:5432/db" -ForegroundColor Gray
Write-Host ""
if ($networkIPs.Count -gt 0) {
    Write-Host "Local Network IPs (for ALLOWED_HOSTS):" -ForegroundColor Yellow
    foreach ($ip in $networkIPs) {
        Write-Host "   - $ip" -ForegroundColor White
    }
} else {
    Write-Host "Local Network IP:" -ForegroundColor Yellow
    Write-Host "   ⚠️  Not detected - check your network connection" -ForegroundColor Yellow
}
Write-Host ""
pause





