#!/bin/bash

echo "================================================================================"
echo "PROFESSIONAL CONSULTATION PRICE IMPORT - DOCKER"
echo "================================================================================"
echo ""

# Find container name
CONTAINER_NAME=$(docker ps --format "{{.Names}}" | grep -E "web|hms|django" | head -n 1)

if [ -z "$CONTAINER_NAME" ]; then
    echo "ERROR: Could not find running container"
    echo "Please ensure Docker containers are running"
    exit 1
fi

echo "Found container: $CONTAINER_NAME"
echo ""

# Check if file exists in container
echo "Checking for Excel file..."
docker exec "$CONTAINER_NAME" test -f "hms/prices/Consult Price List 2025(1).xlsx"

if [ $? -ne 0 ]; then
    echo "WARNING: Excel file not found in container"
    echo "Please copy the file to: hms/prices/Consult Price List 2025(1).xlsx"
    echo ""
    echo "Or use: docker cp 'Consult Price List 2025(1).xlsx' $CONTAINER_NAME:/app/hms/prices/"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "Starting import..."
echo ""

# Run import with verbose output
docker exec -it "$CONTAINER_NAME" python manage.py import_consultation_prices --verbose

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo "IMPORT COMPLETE!"
    echo "================================================================================"
    echo ""
    echo "View prices at: http://localhost:8000/hms/pricing/"
    echo ""
else
    echo ""
    echo "================================================================================"
    echo "IMPORT FAILED"
    echo "================================================================================"
    echo ""
    echo "Please check the error messages above"
    echo ""
    exit 1
fi








