#!/bin/bash
# Deploy Drug Accountability System to Docker
# Run this from your project root directory

set -e  # Exit on error

echo "=========================================="
echo "Deploying Drug Accountability System"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Checking Docker containers...${NC}"
docker-compose ps

echo ""
echo -e "${YELLOW}Step 2: Running database migration...${NC}"
docker-compose exec web python manage.py migrate hospital 1058_add_drug_accountability_system

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migration completed successfully!${NC}"
else
    echo -e "${RED}✗ Migration failed. Trying all pending migrations...${NC}"
    docker-compose exec web python manage.py migrate
fi

echo ""
echo -e "${YELLOW}Step 3: Restarting web service...${NC}"
docker-compose restart web

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "The web service is restarting..."
echo "Wait a few seconds, then test:"
echo "  http://192.168.2.216:8000/hms/drug-returns/"
echo ""
echo "To check logs:"
echo "  docker-compose logs -f web"
echo ""







