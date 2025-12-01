# Docker Desktop IP Explanation

## Understanding Docker Desktop IPs

When working with Docker Desktop on Windows, there are two important IP addresses to understand:

### 1. **Docker Desktop Host IP** (`host.docker.internal`)

This is a **special DNS name** that Docker Desktop provides. You don't need to know the actual IP address - just use `host.docker.internal` in your configuration.

**Use this for:**
- Database connections from Docker containers to services on your host machine
- Example: `DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/db`

**Why it's "unknown":**
- Docker Desktop manages this automatically
- The actual IP can change, but `host.docker.internal` always works
- You don't need to find or configure this IP manually

### 2. **Your Local Network IP** (e.g., `192.168.2.216`)

This is your computer's IP address on your local network (WiFi/LAN). This is what other devices use to access your Docker services.

**Use this for:**
- `ALLOWED_HOSTS` in Django settings
- `CSRF_TRUSTED_ORIGINS` in Django settings
- Accessing your app from other devices on the network

**How to find it:**
- Run: `detect_docker_ip.bat`
- Or run: `ipconfig` and look for "IPv4 Address"
- Or run: `powershell -ExecutionPolicy Bypass -File detect_docker_ip.ps1`

## Current Configuration

Based on your system, I've detected:
- **Main Network IP**: `192.168.2.216` (for network access)
- **Docker Network IP**: `172.19.144.1` (Docker Desktop's internal network)

Both have been added to your `docker-compose.yml` file.

## Quick Reference

| Purpose | What to Use | Example |
|---------|-------------|---------|
| Database connection from Docker | `host.docker.internal` | `postgresql://user:pass@host.docker.internal:5432/db` |
| Network access from other devices | Your local IP | `http://192.168.2.216:8000` |
| Local access (same computer) | `localhost` or `127.0.0.1` | `http://localhost:8000` |

## Troubleshooting

### "Docker Desktop IP is unknown"
This is **normal** and **not a problem**! You should use `host.docker.internal` instead of trying to find the actual IP.

### "Can't access from network"
1. Make sure your IP is in `ALLOWED_HOSTS` in `docker-compose.yml`
2. Make sure your IP is in `CSRF_TRUSTED_ORIGINS` in `docker-compose.yml`
3. Restart Docker services: `docker-compose restart web`
4. Check Windows Firewall allows port 8000

### "Database connection fails"
- Use `host.docker.internal` (not `localhost` or your network IP)
- Make sure PostgreSQL is running on your host machine
- Check the port (usually 5432)

## Tools Provided

1. **detect_docker_ip.bat** - Simple batch file to detect your network IP
2. **detect_docker_ip.ps1** - PowerShell script with more features
3. **configure_network_access.ps1** - Automatically updates docker-compose.yml with detected IPs

Run any of these to detect and configure your IP addresses automatically.





