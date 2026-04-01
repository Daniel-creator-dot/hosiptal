#!/bin/bash
# Script to update Robbert to superuser in Docker environment

echo "=========================================="
echo "Making Robbert a Superuser in Docker"
echo "=========================================="
echo ""

# Option 1: Using Django management command
echo "Method 1: Using Django management command..."
docker-compose exec web python manage.py make_robbert_superuser

# Option 2: Using Django shell
echo ""
echo "Method 2: Using Django shell..."
docker-compose exec web python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()

# Find Robbert
user = None
for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
    try:
        user = User.objects.get(username=username)
        break
    except User.DoesNotExist:
        continue

if not user:
    users = User.objects.filter(username__icontains='robbert')
    if users.exists():
        user = users.first()

if user:
    user.is_superuser = True
    user.is_staff = True
    user.is_active = True
    user.save()
    print(f"✅ Updated {user.username} to superuser")
    print(f"   is_superuser: {user.is_superuser}")
    print(f"   is_staff: {user.is_staff}")
    print(f"   is_active: {user.is_active}")
else:
    print("❌ User 'robbert' not found!")
EOF

echo ""
echo "=========================================="
echo "✅ Update Complete!"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT: Robbert must log out and log back in for changes to take effect!"
echo ""






