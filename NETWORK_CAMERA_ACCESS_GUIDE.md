# Network Camera Access Guide

## Problem
Camera access requires **HTTPS or localhost** for security. When other machines on the network access via HTTP (like `http://192.168.x.x:8000`), the camera won't work.

## Solution: Enable HTTPS for Network Access

### Option 1: Quick Setup (Recommended for Development)

1. **Install django-extensions** (if not already installed):
   ```bash
   pip install django-extensions
   ```

2. **Run the setup script**:
   ```bash
   python setup_https_for_camera.py
   ```

3. **Start server with HTTPS**:
   ```bash
   python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000
   ```

4. **Access from other machines**:
   - Find your server's IP address (e.g., `192.168.2.216`)
   - Access via: `https://192.168.2.216:8000`
   - Browser will show security warning → Click "Advanced" → "Proceed"

### Option 2: Manual Certificate Generation

If you prefer to do it manually:

1. **Create certs directory**:
   ```bash
   mkdir certs
   ```

2. **Generate self-signed certificate** (requires OpenSSL):
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost"
   ```

3. **Start server**:
   ```bash
   python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000
   ```

### Option 3: Production Setup (Nginx + Let's Encrypt)

For production, use a reverse proxy with proper SSL:

1. **Install Nginx**
2. **Get Let's Encrypt certificate** (free SSL):
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```
3. **Configure Nginx** to proxy to Django (see `deployment/hms-nginx.conf`)

## Important Notes

### Self-Signed Certificate Warning
- Browsers will show "Not Secure" warning
- This is **normal** for local network use
- Click "Advanced" → "Proceed to site" to continue
- The camera will work after accepting the certificate

### Finding Your IP Address

**Windows:**
```bash
ipconfig
# Look for IPv4 Address (e.g., 192.168.2.216)
```

**Linux/Mac:**
```bash
ip addr show
# or
ifconfig
```

### Firewall
Make sure port 8000 (or your HTTPS port) is open:
- Windows Firewall: Allow port 8000
- Linux: `sudo ufw allow 8000/tcp`

## Testing

1. **On the server machine**: Access `https://localhost:8000` → Camera should work
2. **On network machines**: Access `https://YOUR_IP:8000` → Camera should work
3. **If camera doesn't work**: Check browser console (F12) for errors

## Troubleshooting

### "Certificate Error" in Browser
- This is expected with self-signed certificates
- Click "Advanced" → "Proceed to site"
- Or add exception in browser settings

### "Connection Refused"
- Check firewall settings
- Verify server is running on `0.0.0.0:8000` (not just `127.0.0.1`)
- Check if port 8000 is accessible

### "Camera Still Not Working"
- Make sure you're using `https://` (not `http://`)
- Check browser console (F12) for detailed errors
- Verify camera permissions are allowed

---

**Status**: ✅ Ready to use
**Last Updated**: 2025-01-14
