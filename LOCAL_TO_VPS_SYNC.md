# Local to VPS Sync Guide

## Your Setup
- **Local Directory**: `C:\Users\user\chm` (Windows)
- **GitHub Repository**: `jerry6193/primemed`
- **VPS Directory**: `/root/primemed` (Linux)

## Workflow: Local → GitHub → VPS

### Step 1: Push Changes from Local to GitHub

On your **local Windows machine** (`C:\Users\user\chm`):

```bash
# Navigate to your local project
cd C:\Users\user\chm

# Check status
git status

# Add all changes
git add .

# Commit changes
git commit -m "Your commit message"

# Push to GitHub
git push origin main
```

### Step 2: Pull Changes on VPS

On your **VPS** (`/root/primemed`):

```bash
# Connect via PuTTY first, then:
cd ~/primemed

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install any new dependencies
pip install -r requirements.txt

# Run migrations if needed
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart server (if using gunicorn/systemd)
# Or just restart: python manage.py runserver 0.0.0.0:8000
```

## Quick Sync Scripts

### Local Script (Windows - PowerShell)

Create `sync_to_vps.ps1` in `C:\Users\user\chm`:

```powershell
# Sync to VPS via GitHub
Write-Host "🔄 Syncing to VPS..." -ForegroundColor Cyan

# Check for changes
git status

# Add all changes
git add .

# Commit
$message = Read-Host "Enter commit message"
git commit -m $message

# Push to GitHub
Write-Host "📤 Pushing to GitHub..." -ForegroundColor Yellow
git push origin main

Write-Host "✅ Pushed to GitHub!" -ForegroundColor Green
Write-Host "Now run 'git pull' on your VPS" -ForegroundColor Cyan
```

### VPS Script (Linux)

Create `pull_and_deploy.sh` in `/root/primemed`:

```bash
#!/bin/bash
cd ~/primemed
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
echo "✅ Updated from GitHub!"
```

## Automated Deployment (Optional)

### Option 1: GitHub Webhook

Set up a webhook on GitHub that automatically pulls on VPS when you push.

### Option 2: Simple Sync Script

**On Local (Windows):**
```powershell
# sync.ps1
git add .
git commit -m "Update"
git push origin main
Write-Host "Run on VPS: cd ~/primemed && git pull && source venv/bin/activate && python manage.py migrate"
```

**On VPS:**
```bash
# Quick update command
cd ~/primemed && source venv/bin/activate && git pull origin main && pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

## Daily Workflow

1. **Make changes locally** in `C:\Users\user\chm`
2. **Test locally** (if possible)
3. **Commit and push**:
   ```bash
   cd C:\Users\user\chm
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```
4. **Pull on VPS**:
   ```bash
   ssh root@45.8.225.73
   cd ~/primemed
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

## Quick Commands Reference

### Local (Windows)
```powershell
# Navigate
cd C:\Users\user\chm

# Check status
git status

# Push changes
git add .
git commit -m "Update"
git push origin main
```

### VPS (Linux)
```bash
# Connect
ssh root@45.8.225.73

# Navigate
cd ~/primemed

# Pull updates
git pull origin main

# Activate environment
source venv/bin/activate

# Update
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

## Troubleshooting

### Local: "Not a git repository"
```bash
cd C:\Users\user\chm
git init
git remote add origin https://github.com/jerry6193/primemed.git
git pull origin main
```

### VPS: "Permission denied"
```bash
# Check git remote
cd ~/primemed
git remote -v

# If needed, update remote
git remote set-url origin https://github.com/jerry6193/primemed.git
```

### VPS: "Merge conflicts"
```bash
# If you have local changes on VPS
git stash
git pull origin main
git stash pop
# Resolve conflicts, then commit
```







