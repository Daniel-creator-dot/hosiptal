#!/bin/bash
# Deployment script for Drug Accountability System
# Run this on your remote server

set -e  # Exit on error

echo "=========================================="
echo "Deploying Drug Accountability System"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo -e "${RED}Error: manage.py not found. Please run this script from your Django project root.${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Checking for required files...${NC}"

# Check if required files exist
REQUIRED_FILES=(
    "hospital/urls.py"
    "hospital/views_drug_accountability.py"
    "hospital/views_departments.py"
    "hospital/migrations/1058_add_drug_accountability_system.py"
    "hospital/models_drug_accountability.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: Required file $file not found!${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Found: $file${NC}"
    fi
done

echo -e "${YELLOW}Step 2: Running database migrations...${NC}"

# Run the specific migration
python manage.py migrate hospital 1058_add_drug_accountability_system

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migration completed successfully!${NC}"
else
    echo -e "${RED}Error: Migration failed!${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 3: Verifying migration...${NC}"

# Check if tables were created
python manage.py shell << EOF
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'hospital_drug%';")
tables = cursor.fetchall()
if any('drugreturn' in str(t).lower() for t in tables):
    print("✓ DrugReturn table exists")
else:
    print("✗ DrugReturn table not found")
    exit(1)
EOF

echo -e "${YELLOW}Step 4: Testing URL registration...${NC}"

# Test if URLs are registered
python manage.py shell << EOF
from django.urls import reverse, NoReverseMatch
try:
    url = reverse('hospital:drug_returns_list')
    print(f"✓ URL registered: {url}")
except NoReverseMatch as e:
    print(f"✗ URL not registered: {e}")
    exit(1)
EOF

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Restart your Django server"
echo "2. Visit: http://your-server:8000/hms/drug-returns/"
echo "3. The page should now work without errors"
echo ""







