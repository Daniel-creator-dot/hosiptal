# Ensures HMS Docker always runs from C:\chm (canonical SSD project root).
param(
    [switch]$Quiet,
    [switch]$Fix
)

$CanonicalRoot = 'C:\chm'
$LegacyRoot = 'D:\chm'

function Write-Status([string]$Message, [string]$Color = 'White') {
    if (-not $Quiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

if (-not (Test-Path $CanonicalRoot)) {
    Write-Status "ERROR: Canonical HMS root not found: $CanonicalRoot" 'Red'
    exit 1
}

Set-Location $CanonicalRoot

$mountRoot = $null
$webRunning = $false
try {
    $mountJson = docker inspect chm-web-1 --format '{{json .Mounts}}' 2>$null
    if ($LASTEXITCODE -eq 0 -and $mountJson) {
        $webRunning = $true
        $mounts = $mountJson | ConvertFrom-Json
        $appMount = $mounts | Where-Object { $_.Destination -eq '/app' } | Select-Object -First 1
        if ($appMount) {
            $mountRoot = ($appMount.Source -replace '/', '\').TrimEnd('\')
        }
    }
} catch {
    # Container may not exist yet.
}

$mountOk = $mountRoot -and ($mountRoot -ieq $CanonicalRoot)
$needsFix = $webRunning -and -not $mountOk

if ($mountOk) {
    Write-Status "OK: HMS is running from $CanonicalRoot" 'Green'
} elseif ($webRunning) {
    Write-Status "WARNING: chm-web-1 is mounted from $mountRoot (expected $CanonicalRoot)" 'Yellow'
} else {
    Write-Status "INFO: HMS web container not running; will start from $CanonicalRoot" 'Cyan'
}

if (Test-Path $LegacyRoot) {
    Write-Status "NOTE: Legacy copy exists at $LegacyRoot - do not run docker compose from there." 'DarkYellow'
}

if ($needsFix) {
    if ($Fix -or -not $Quiet) {
        Write-Status "Recreating Docker stack from $CanonicalRoot..." 'Yellow'
        docker compose down 2>$null | Out-Null
        docker compose up -d
        if ($LASTEXITCODE -ne 0) {
            Write-Status "ERROR: Failed to start Docker from $CanonicalRoot" 'Red'
            exit 1
        }
        Start-Sleep -Seconds 3
        $mountJson = docker inspect chm-web-1 --format '{{json .Mounts}}' 2>$null
        if ($mountJson) {
            $mounts = $mountJson | ConvertFrom-Json
            $appMount = $mounts | Where-Object { $_.Destination -eq '/app' } | Select-Object -First 1
            $newRoot = ($appMount.Source -replace '/', '\').TrimEnd('\')
            if ($newRoot -ieq $CanonicalRoot) {
                Write-Status "Fixed: HMS now runs from $CanonicalRoot" 'Green'
            } else {
                Write-Status "ERROR: Mount still wrong after recreate: $newRoot" 'Red'
                exit 1
            }
        }
    } else {
        exit 2
    }
} elseif (-not $webRunning) {
    if ($Fix) {
        Write-Status "Starting HMS from $CanonicalRoot..." 'Yellow'
        docker compose up -d
        if ($LASTEXITCODE -ne 0) {
            Write-Status "ERROR: Failed to start Docker from $CanonicalRoot" 'Red'
            exit 1
        }
        Write-Status "Started HMS from $CanonicalRoot" 'Green'
    }
}

exit 0
