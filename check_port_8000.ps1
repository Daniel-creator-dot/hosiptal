# Wait 5 seconds
Start-Sleep -Seconds 5

# Check port 8000 and get process IDs
$portConnections = netstat -ano | findstr :8000

if ($LASTEXITCODE -eq 0 -and $portConnections) {
    Write-Host "Port 8000 is in use:" -ForegroundColor Yellow
    Write-Host $portConnections
    
    # Extract unique process IDs
    $processIds = $portConnections | ForEach-Object {
        if ($_ -match '\s+(\d+)$') {
            $matches[1]
        }
    } | Sort-Object -Unique
    
    Write-Host "`nFound Process IDs: $($processIds -join ', ')" -ForegroundColor Cyan
    
    # Check for duplicates (same PID appearing multiple times)
    $duplicatePids = $processIds | Group-Object | Where-Object { $_.Count -gt 1 }
    
    if ($duplicatePids) {
        Write-Host "`nWarning: Found duplicate process entries" -ForegroundColor Red
        foreach ($dup in $duplicatePids) {
            Write-Host "  PID $($dup.Name) appears $($dup.Count) times" -ForegroundColor Red
        }
    } else {
        Write-Host "`nNo duplicate process IDs found" -ForegroundColor Green
    }
    
    # Show process details
    Write-Host "`nProcess Details:" -ForegroundColor Cyan
    foreach ($pid in $processIds) {
        try {
            $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "  PID $pid : $($process.ProcessName) - $($process.Path)" -ForegroundColor White
            } else {
                Write-Host "  PID $pid : Process not found (may have terminated)" -ForegroundColor Gray
            }
        } catch {
            Write-Host "  PID $pid : Error retrieving process info - $($_.Exception.Message)" -ForegroundColor Red
        }
    }
} else {
    Write-Host "Port 8000 is not in use" -ForegroundColor Green
}






