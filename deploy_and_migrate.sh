#!/bin/bash
# Complete deployment script - Run this on your REMOTE server
# This script deploys files and runs the migration

set -e  # Exit on error

echo "=========================================="
echo "Drug Accountability System - Full Deployment"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo -e "${RED}Error: manage.py not found. Please run from Django project root (/app)${NC}"
    exit 1
fi

PROJECT_ROOT=$(pwd)
HOSPITAL_DIR="$PROJECT_ROOT/hospital"

echo -e "${YELLOW}Step 1: Verifying required files exist...${NC}"

# Check required files
REQUIRED_FILES=(
    "$HOSPITAL_DIR/urls.py"
    "$HOSPITAL_DIR/views_drug_accountability.py"
    "$HOSPITAL_DIR/views_departments.py"
    "$HOSPITAL_DIR/models_drug_accountability.py"
    "$HOSPITAL_DIR/migrations/1058_add_drug_accountability_system.py"
    "$HOSPITAL_DIR/templates/hospital/pharmacy_dashboard_worldclass.html"
)

MISSING_FILES=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}✗ Missing: $file${NC}"
        MISSING_FILES=1
    else
        echo -e "${GREEN}✓ Found: $file${NC}"
    fi
done

if [ $MISSING_FILES -eq 1 ]; then
    echo -e "${RED}Error: Some required files are missing. Please copy them first.${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Running database migration...${NC}"

# Run the migration
python manage.py migrate hospital 1058_add_drug_accountability_system

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migration completed successfully!${NC}"
else
    echo -e "${RED}✗ Migration failed!${NC}"
    echo -e "${YELLOW}Attempting to run all pending migrations...${NC}"
    python manage.py migrate
fi

echo ""
echo -e "${YELLOW}Step 3: Verifying tables were created...${NC}"

# Check if tables exist
python manage.py shell << 'PYTHON_EOF'
from django.db import connection
cursor = connection.cursor()

tables_to_check = ['hospital_drugreturn', 'hospital_drugadministrationinventory']
all_exist = True

for table in tables_to_check:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, [table])
    exists = cursor.fetchone()[0]
    if exists:
        print(f"✓ Table exists: {table}")
    else:
        print(f"✗ Table missing: {table}")
        all_exist = False

if not all_exist:
    exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tables verified!${NC}"
else
    echo -e "${RED}✗ Some tables are missing. Migration may have failed.${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 4: Testing URL registration...${NC}"

python manage.py shell << 'PYTHON_EOF'
from django.urls import reverse, NoReverseMatch

urls_to_test = [
    'hospital:drug_returns_list',
    'hospital:inventory_accountability_dashboard',
    'hospital:inventory_history',
]

all_ok = True
for url_name in urls_to_test:
    try:
        url = reverse(url_name)
        print(f"✓ URL registered: {url_name} -> {url}")
    except NoReverseMatch as e:
        print(f"✗ URL not found: {url_name}")
        all_ok = False

if not all_ok:
    exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All URLs registered correctly!${NC}"
else
    echo -e "${RED}✗ Some URLs are not registered. Check urls.py${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Restart your Django server:"
echo "   python manage.py runserver 0.0.0.0:8000"
echo ""
echo "2. Test the URLs:"
echo "   http://192.168.2.216:8000/hms/drug-returns/"
echo "   http://192.168.2.216:8000/hms/pharmacy/"
echo ""







