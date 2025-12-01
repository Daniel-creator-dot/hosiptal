#!/bin/bash

# ========================================
# 🐳 DOCKER BUILD & PUSH TO DOCKER HUB
# ========================================

echo ""
echo "========================================"
echo "  🐳 HMS DOCKER BUILD & PUSH"
echo "========================================"
echo ""

# Check if Docker is running
echo "[1/4] Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "   ❌ ERROR: Docker is not running!"
    echo "   Please start Docker and try again."
    echo ""
    exit 1
fi
echo "   ✅ Docker is running"
echo ""

# Get Docker Hub username
echo "[2/4] Docker Hub Configuration..."
read -p "Enter your Docker Hub username: " DOCKER_USERNAME

if [ -z "$DOCKER_USERNAME" ]; then
    echo "   ❌ ERROR: Docker Hub username is required!"
    exit 1
fi

# Set image name and tag
IMAGE_NAME="${DOCKER_USERNAME}/hms"
TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${TAG}"

echo "   Image: ${FULL_IMAGE}"
echo ""

# Login to Docker Hub
echo "[3/4] Logging into Docker Hub..."
docker login
if [ $? -ne 0 ]; then
    echo "   ❌ ERROR: Failed to login to Docker Hub!"
    exit 1
fi
echo "   ✅ Logged in successfully"
echo ""

# Build the image
echo "[4/4] Building Docker image..."
echo "   This may take several minutes..."
docker build -t "${FULL_IMAGE}" .
if [ $? -ne 0 ]; then
    echo "   ❌ ERROR: Failed to build Docker image!"
    exit 1
fi
echo "   ✅ Build complete"
echo ""

# Push the image
echo "[5/5] Pushing to Docker Hub..."
echo "   This may take several minutes depending on your connection..."
docker push "${FULL_IMAGE}"
if [ $? -ne 0 ]; then
    echo "   ❌ ERROR: Failed to push Docker image!"
    exit 1
fi
echo "   ✅ Push complete"
echo ""

echo "========================================"
echo "  ✅ SUCCESS!"
echo "========================================"
echo ""
echo "🐳 Your image is now available at:"
echo "   https://hub.docker.com/r/${DOCKER_USERNAME}/hms"
echo ""
echo "📋 To run this image:"
echo "   docker run -p 8000:8000 ${FULL_IMAGE}"
echo ""
echo "   Or use docker-compose.yml with:"
echo "   docker-compose up -d"
echo ""

