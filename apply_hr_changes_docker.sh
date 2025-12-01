#!/bin/bash
# ========================================
# Apply HR Manager Changes to Docker
# ========================================

echo ""
echo "========================================"
echo "  Applying HR Manager Changes to Docker"
echo "========================================"
echo ""

# Check if Docker is running
echo "[1/7] Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "   ❌ ERROR: Docker is not running!"
    echo "   Please start Docker Desktop and try again."
    exit 1
fi
echo "   ✅ Docker is running"
echo ""

# Check if containers are running
echo "[2/7] Checking Docker containers..."
if ! docker-compose ps | grep -q "Up"; then
    echo "   ⚠️  Containers are not running. Starting them..."
    docker-compose up -d
    sleep 5
else
    echo "   ✅ Containers are running"
fi
echo ""

# Create migration for model changes
echo "[3/7] Creating database migration for HR Manager profession..."
docker-compose exec -T web python manage.py makemigrations hospital
if [ $? -ne 0 ]; then
    echo "   ⚠️  Warning: Migration creation had issues (may already exist)"
else
    echo "   ✅ Migration created"
fi
echo ""

# Run migrations
echo "[4/7] Running database migrations..."
docker-compose exec -T web python manage.py migrate
if [ $? -ne 0 ]; then
    echo "   ❌ ERROR: Migrations failed"
    exit 1
fi
echo "   ✅ Migrations complete"
echo ""

# Create default groups (ensures HR Manager group exists)
echo "[5/7] Creating/updating role groups..."
docker-compose exec -T web python manage.py shell << 'EOF'
from hospital.utils_roles import create_default_groups
create_default_groups()
print('✅ Role groups updated')
EOF
if [ $? -ne 0 ]; then
    echo "   ⚠️  Warning: Group creation had issues"
else
    echo "   ✅ Role groups ready"
fi
echo ""

# Assign HR Manager role to Nana Yaa B. Asamoah
echo "[6/7] Assigning HR Manager role to Nana Yaa B. Asamoah..."
docker-compose exec -T web python manage.py assign_hr_manager --name "Nana Yaa B. Asamoah"
if [ $? -ne 0 ]; then
    echo "   ⚠️  Warning: Role assignment had issues (user may not exist yet)"
    echo "   You can run this manually: docker-compose exec web python manage.py assign_hr_manager --name \"Nana Yaa B. Asamoah\""
else
    echo "   ✅ HR Manager role assigned"
fi
echo ""

# Restart web container to apply code changes
echo "[7/7] Restarting web container to apply code changes..."
docker-compose restart web
sleep 3
echo "   ✅ Web container restarted"
echo ""

echo "========================================"
echo "  ✅ CHANGES APPLIED TO DOCKER!"
echo "========================================"
echo ""
echo "📋 Summary:"
echo "   - Model changes: HR Manager profession added"
echo "   - Database migrations: Applied"
echo "   - Role groups: Updated"
echo "   - User assignment: Nana Yaa B. Asamoah → HR Manager"
echo "   - Web container: Restarted"
echo ""
echo "🌐 Access your application:"
echo "   http://localhost:8000"
echo ""
echo "📋 To verify HR Manager access:"
echo "   docker-compose exec web python manage.py assign_hr_manager --name \"Nana Yaa B. Asamoah\""
echo ""


