# 🐳 Docker Desktop Update Guide

## Current Version
- **Docker**: 29.1.3
- **Docker Compose**: v2.40.3-desktop.1

## Update Methods

### Method 1: Using Docker Desktop Built-in Updater (Recommended)

1. **Open Docker Desktop**
   - Click the Docker icon in your system tray (bottom-right corner)
   - Or search for "Docker Desktop" in Start menu

2. **Check for Updates**
   - Click the **gear icon** (⚙️) to open Settings
   - Navigate to **Software Updates** section
   - Click **Check for Updates**
   - If an update is available, follow the prompts to download and install

3. **Restart Docker Desktop**
   - After installation, Docker Desktop will restart automatically
   - Wait for it to fully start (whale icon should be steady)

### Method 2: Using Windows Package Manager (winget)

1. **Open PowerShell as Administrator**
   - Press `Win + X`
   - Select "Windows PowerShell (Admin)" or "Terminal (Admin)"

2. **Update Docker Desktop**
   ```powershell
   winget upgrade Docker.DockerDesktop
   ```

3. **Restart Docker Desktop**
   - Close and reopen Docker Desktop
   - Wait for it to fully start

### Method 3: Manual Download and Install

1. **Download Latest Version**
   - Visit: https://www.docker.com/products/docker-desktop/
   - Click "Download for Windows"
   - Run the installer

2. **Install**
   - Run the downloaded installer
   - Follow the installation wizard
   - Restart Docker Desktop when prompted

## After Updating

### Verify Update
```powershell
docker --version
docker-compose --version
```

### Restart Your Containers
```powershell
cd D:\chm
docker-compose down
docker-compose up -d
```

### Check Container Status
```powershell
docker-compose ps
```

## Troubleshooting

### If Docker Won't Start After Update

1. **Restart Windows**
   - Sometimes a full restart is needed after Docker updates

2. **Check WSL 2**
   - Docker Desktop requires WSL 2 on Windows
   - Verify: `wsl --status`
   - Update if needed: `wsl --update`

3. **Reset Docker Desktop**
   - Open Docker Desktop Settings
   - Go to **Troubleshoot**
   - Click **Reset to factory defaults** (if needed)

### If Containers Won't Start

1. **Rebuild Images**
   ```powershell
   docker-compose build --no-cache
   docker-compose up -d
   ```

2. **Check Logs**
   ```powershell
   docker-compose logs web
   ```

## Important Notes

- ⚠️ **Backup your data** before updating (if you have important volumes)
- ⚠️ **Stop all containers** before updating to avoid data loss
- ✅ Docker Desktop updates are usually safe and preserve your containers
- ✅ Your `docker-compose.yml` and project files won't be affected

## Current Project Status

Your project uses:
- Docker Compose for orchestration
- PostgreSQL database
- Redis for caching
- Multiple services (web, celery, etc.)

After updating, make sure all services start correctly:
```powershell
docker-compose ps
```








