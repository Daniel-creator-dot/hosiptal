#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple HTTPS setup for Django - enables camera access on network
Uses Python's built-in SSL (no OpenSSL required)
"""
import os
import sys
from pathlib import Path

def create_cert_with_python():
    """Create self-signed certificate using Python (no OpenSSL needed)"""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta
    except ImportError:
        print("Installing cryptography library...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'cryptography'])
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta
    
    cert_dir = Path(__file__).parent / 'certs'
    cert_dir.mkdir(exist_ok=True)
    
    cert_file = cert_dir / 'server.crt'
    key_file = cert_dir / 'server.key'
    
    if cert_file.exists() and key_file.exists():
        print(f"[OK] Certificate already exists")
        return str(cert_file), str(key_file)
    
    print("Generating self-signed certificate...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    import ipaddress
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "GH"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Hospital Management System"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
    ).not_valid_after(
        (datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()) + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.DNSName("127.0.0.1"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    
    # Write certificate
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # Write private key
    with open(key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    print(f"[OK] Certificate created: {cert_file}")
    return str(cert_file), str(key_file)

if __name__ == '__main__':
    import sys
    # Fix encoding for Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    cert_file, key_file = create_cert_with_python()
    if cert_file:
        print("\n[OK] Setup complete!")
        print("\nTo start server with HTTPS:")
        print("  python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000")
        print("\nOr run: START_HTTPS_SERVER.bat")
