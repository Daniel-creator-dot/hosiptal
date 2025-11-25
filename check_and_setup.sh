#!/bin/bash
# Check for errors and set up HMS on VPS

echo "🔍 Checking system and setting up HMS..."

# Check current directory
echo "📍 Current directory: $(pwd)"

# Check Python
echo "🐍 Checking Python..."
python3 --version || echo "❌ Python3 not found!"
which python3 || echo "❌ Python3 not in PATH!"

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ ERROR: manage.py not found! Are you in the project directory?"
    echo "Run: cd ~/primemed"
    exit 1
fi

echo "✅ Found manage.py - we're in the right directory"

# Check for requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo "❌ ERROR: requirements.txt not found!"
    exit 1
fi

echo "✅ Found requirements.txt"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Check pip
echo "📦 Checking pip..."
pip --version || echo "❌ pip not found!"

# Install/upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Check PostgreSQL
echo "🗄️  Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    echo "✅ PostgreSQL installed"
    sudo systemctl status postgresql --no-pager | head -3
else
    echo "⚠️  PostgreSQL not found - you may need to install it"
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: .env file not found!"
    echo "Creating .env template..."
    cat > .env << EOF
DEBUG=False
SECRET_KEY=CHANGE-THIS-TO-A-RANDOM-SECRET-KEY
DATABASE_URL=postgresql://hms_user:password@localhost:5432/hms_db
ALLOWED_HOSTS=45.8.225.73
EOF
    echo "✅ Created .env template - EDIT IT WITH YOUR VALUES!"
else
    echo "✅ .env file exists"
fi

# Check Django
echo "🔍 Checking Django installation..."
python manage.py --version || echo "❌ Django not installed - will install dependencies"

# Try to check for common errors
echo ""
echo "🔍 Running Django system check..."
python manage.py check --deploy 2>&1 | head -20

echo ""
echo "✅ Setup check complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your settings"
echo "2. Run: pip install -r requirements.txt"
echo "3. Run: python manage.py migrate"
echo "4. Run: python manage.py collectstatic --noinput"







