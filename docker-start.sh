#!/bin/bash
# Docker startup script with network configuration
# This script detects your local IP and configures Docker for network access

echo "🚀 Starting HMS Docker containers with network access..."

# Detect local network IP (most common WiFi interface)
LOCAL_IP=$(ip route get 8.8.8.8 2>/dev/null | grep -oP 'src \K\S+' | head -1)

# Fallback for Windows/WSL or if detection fails
if [ -z "$LOCAL_IP" ]; then
    # Try common network interfaces
    if command -v ipconfig >/dev/null 2>&1; then
        # Windows - extract IP from ipconfig
        LOCAL_IP=$(ipconfig | grep -i "IPv4" | grep -oP '\d+\.\d+\.\d+\.\d+' | grep -v "127.0.0.1" | head -1)
    elif command -v hostname >/dev/null 2>&1; then
        # Try hostname -I
        LOCAL_IP=$(hostname -I | awk '{print $1}')
    fi
fi

# Default fallback
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="192.168.1.100"
    echo "⚠️  Could not detect local IP, using default: $LOCAL_IP"
    echo "   Please update CSRF_TRUSTED_ORIGINS in docker-compose.yml with your actual IP"
else
    echo "✅ Detected local IP: $LOCAL_IP"
fi

# Export for docker-compose
export LOCAL_IP

# Build and start containers
echo "📦 Building and starting containers..."
docker-compose up -d --build

echo ""
echo "✅ HMS is now running!"
echo ""
echo "🌐 Access the application at:"
echo "   - Local: http://localhost:8000"
echo "   - Network: http://$LOCAL_IP:8000"
echo ""
echo "📝 To access from other devices on your network:"
echo "   1. Make sure they're on the same WiFi network"
echo "   2. Use: http://$LOCAL_IP:8000"
echo ""
echo "🔧 To view logs: docker-compose logs -f web"
echo "🛑 To stop: docker-compose down"






