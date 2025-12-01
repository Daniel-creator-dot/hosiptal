@echo off
REM HMS Auto-Start Script
REM Waits for Docker Desktop and starts HMS services

REM Change to project directory
cd /d "%~dp0"

REM Wait for Docker Desktop to be ready (up to 2 minutes)
echo Waiting for Docker Desktop to start...
set MAX_WAIT=24
set WAIT_COUNT=0

:wait_docker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo Docker Desktop is ready!
    goto docker_ready
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% geq %MAX_WAIT% (
    echo ERROR: Docker Desktop did not start within 2 minutes
    echo Please start Docker Desktop manually
    exit /b 1
)
goto wait_docker

:docker_ready
echo Starting HMS services...
docker-compose up -d

REM Log the startup
echo HMS services started at %date% %time% >> startup_log.txt











