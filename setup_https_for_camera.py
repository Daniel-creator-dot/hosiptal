#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup HTTPS for Django development server to enable camera access on network
This creates a self-signed certificate for local network use
"""
import os
import subprocess
import sys
from pathlib import Path

def generate_self_signed_cert():
    """Generate a self-signed SSL certificate for local network use"""
    cert_dir = Path(__file__).parent / 'certs'
    cert_dir.mkdir(exist_ok=True)
    
    cert_file = cert_dir / 'server.crt'
    key_file = cert_dir / 'server.key'
    
    # Check if cert already exists
    if cert_file.exists() and key_file.exists():
        print(f"✅ Certificate already exists at {cert_file}")
        return str(cert_file), str(key_file)
    
    print("Generating self-signed certificate for local network...")
    print("This will allow camera access from other machines on your network.")
    print()
    
    # Try using OpenSSL
    try:
        # Get local IP address
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Generate certificate
        cmd = [
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', str(key_file),
            '-out', str(cert_file),
            '-days', '365',
            '-nodes',
            '-subj', f'/CN={hostname}/O=Hospital Management System/C=GH'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Certificate generated successfully!")
            print(f"   Certificate: {cert_file}")
            print(f"   Key: {key_file}")
            print()
            print(f"⚠️  IMPORTANT: This is a self-signed certificate.")
            print(f"   Browsers will show a security warning - click 'Advanced' and 'Proceed'")
            print()
            return str(cert_file), str(key_file)
        else:
            print(f"❌ OpenSSL error: {result.stderr}")
            return None, None
            
    except FileNotFoundError:
        print("❌ OpenSSL not found. Please install OpenSSL:")
        print("   Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print("   Or use: pip install pyopenssl")
        return None, None
    except Exception as e:
        print(f"❌ Error generating certificate: {e}")
        return None, None

def create_runserver_script():
    """Create a script to run Django with HTTPS"""
    script_content = """@echo off
echo Starting Django server with HTTPS for camera access...
echo.
echo Access the server at: https://localhost:8000
echo Or from network: https://YOUR_IP:8000
echo.
echo Note: Browser will show security warning for self-signed certificate.
echo Click "Advanced" and "Proceed" to continue.
echo.
python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000
pause
"""
    
    script_path = Path(__file__).parent / 'START_HTTPS_SERVER.bat'
    script_path.write_text(script_content, encoding='utf-8')
    print(f"✅ Created {script_path}")
    return script_path

if __name__ == '__main__':
    print("=" * 60)
    print("HTTPS Setup for Camera Access on Network")
    print("=" * 60)
    print()
    
    # Check if django-extensions is installed (needed for runserver_plus)
    try:
        import django_extensions
        print("✅ django-extensions is installed")
    except ImportError:
        print("⚠️  django-extensions not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'django-extensions'], check=True)
        print("✅ django-extensions installed")
    
    # Generate certificate
    cert_file, key_file = generate_self_signed_cert()
    
    if cert_file and key_file:
        # Create run script
        script_path = create_runserver_script()
        
        print()
        print("=" * 60)
        print("✅ Setup Complete!")
        print("=" * 60)
        print()
        print("To start the server with HTTPS:")
        print(f"   1. Run: {script_path}")
        print("   2. Or manually: python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000")
        print()
        print("Then access from other machines:")
        print("   https://YOUR_IP_ADDRESS:8000")
        print()
        print("⚠️  Note: Browsers will show a security warning for self-signed certificates.")
        print("   This is normal for local network use. Click 'Advanced' → 'Proceed'")
    else:
        print()
        print("❌ Setup failed. Please install OpenSSL and try again.")
