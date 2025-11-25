# PowerShell script to sync local changes to VPS via GitHub
# Run this from: C:\Users\user\chm

Write-Host "🔄 Syncing Local Changes to VPS via GitHub..." -ForegroundColor Cyan
Write-Host ""

# Check if we're in a git repository
if (-not (Test-Path .git)) {
    Write-Host "❌ Error: Not a git repository!" -ForegroundColor Red
    Write-Host "Run: git init" -ForegroundColor Yellow
    exit 1
}

# Show current status
Write-Host "📊 Current Status:" -ForegroundColor Yellow
git status --short

# Check if there are changes
$changes = git diff --name-only
$staged = git diff --cached --name-only

if (-not $changes -and -not $staged) {
    Write-Host "✅ No changes to commit" -ForegroundColor Green
    Write-Host ""
    Write-Host "Checking if VPS needs update..." -ForegroundColor Cyan
    Write-Host "Run on VPS: cd ~/primemed && git pull origin main" -ForegroundColor Yellow
    exit 0
}

# Add all changes
Write-Host ""
Write-Host "📦 Adding changes..." -ForegroundColor Yellow
git add .

# Get commit message
Write-Host ""
$commitMsg = Read-Host "Enter commit message (or press Enter for default)"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $commitMsg = "Update from local - $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

# Commit
Write-Host ""
Write-Host "💾 Committing changes..." -ForegroundColor Yellow
git commit -m $commitMsg

# Push to GitHub
Write-Host ""
Write-Host "📤 Pushing to GitHub..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Connect to VPS: ssh root@45.8.225.73" -ForegroundColor White
    Write-Host "2. Run: cd ~/primemed" -ForegroundColor White
    Write-Host "3. Run: git pull origin main" -ForegroundColor White
    Write-Host "4. Run: source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Error pushing to GitHub!" -ForegroundColor Red
    Write-Host "Check your GitHub credentials or network connection" -ForegroundColor Yellow
}







