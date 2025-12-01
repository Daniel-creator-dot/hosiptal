#!/bin/bash

# ========================================
# 🚀 RUN HMS FROM DOCKER HUB
# ========================================

echo ""
echo "========================================"
echo "  🚀 HMS DOCKER RUN"
echo "========================================"
echo ""

# Check if Docker is running
echo "[1/3] Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "   ❌ ERROR: Docker is not running!"
    echo "   Please start Docker and try again."
    echo ""
    exit 1
fi
echo "   ✅ Docker is running"
echo ""

# Get Docker Hub username
echo "[2/3] Docker Image Configuration..."
read -p "Enter your Docker Hub username (or 'local' to use local image): " DOCKER_USERNAME

if [ -z "$DOCKER_USERNAME" ] || [ "$DOCKER_USERNAME" == "local" ]; then
    echo "   Using local image..."
    IMAGE_NAME="hms"
else
    IMAGE_NAME="${DOCKER_USERNAME}/hms"
fi

TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${TAG}"

echo "   Image: ${FULL_IMAGE}"
echo ""

# Check if image exists locally, if not pull it
if [ "$DOCKER_USERNAME" != "local" ] && [ -n "$DOCKER_USERNAME" ]; then
    echo "[3/3] Checking for image..."
    if ! docker images "${FULL_IMAGE}" | grep -q "${IMAGE_NAME}"; then
        echo "   Image not found locally. Pulling from Docker Hub..."
        docker pull "${FULL_IMAGE}"
        if [ $? -ne 0 ]; then
            echo "   ❌ ERROR: Failed to pull Docker image!"
            echo "   Make sure you've pushed the image first using docker-build-push.sh"
            exit 1
        fi
        echo "   ✅ Image pulled successfully"
    else
        echo "   ✅ Image found locally"
    fi
else
    echo "[3/3] Using local image..."
fi

echo ""
echo "========================================"
echo "  🚀 STARTING HMS CONTAINER"
echo "========================================"
echo ""

# Stop and remove existing container if it exists
docker stop hms-container 2>/dev/null
docker rm hms-container 2>/dev/null

# Run the container
echo "Starting container..."
docker run -d \
    --name hms-container \
    -p 8000:8000 \
    -e DATABASE_URL=postgresql://hms_user:hms_password@host.docker.internal:5432/hms_db \
    -e REDIS_URL=redis://host.docker.internal:6379/0 \
    -e SECRET_KEY=your-secret-key-change-this \
    -e DEBUG=True \
    -e ALLOWED_HOSTS=* \
    "${FULL_IMAGE}"

if [ $? -ne 0 ]; then
    echo "   ❌ ERROR: Failed to start container!"
    exit 1
fi

echo "   ✅ Container started successfully"
echo ""
echo "========================================"
echo "  ✅ HMS IS RUNNING!"
echo "========================================"
echo ""
echo "🌐 Access your application:"
echo "   http://localhost:8000"
echo ""
echo "📋 Useful Commands:"
echo "   View logs: docker logs -f hms-container"
echo "   Stop: docker stop hms-container"
echo "   Remove: docker rm hms-container"
echo "   Restart: docker restart hms-container"
echo ""
echo "⚠️  NOTE: Make sure PostgreSQL and Redis are running!"
echo "   Use docker-compose up -d to start all services"
echo ""

