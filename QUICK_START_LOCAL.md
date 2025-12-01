# 🚀 Quick Start - Local Server (No Docker)

## ✅ Status
- **Docker containers:** Stopped (except database)
- **Database:** Running on localhost:5432
- **Server:** Ready to start locally

## 🎯 Start the Server

### Option 1: Use the Batch File (Easiest)
```bash
START_LOCAL_SERVER.bat
```

### Option 2: Manual Start
```bash
# 1. Activate virtual environment
venv\Scripts\activate

# 2. Run migrations (if needed)
python manage.py migrate

# 3. Start server
python manage.py runserver 0.0.0.0:8000
```

## 📍 Access Points

- **Main App:** http://localhost:8000
- **Admin:** http://localhost:8000/admin
- **Patient Registration:** http://localhost:8000/hms/patients/new/

## ⚙️ Configuration

- **Database:** PostgreSQL (localhost:5432)
- **Database Name:** hms_db
- **User:** hms_user
- **Password:** hms_password

## 🔧 Troubleshooting

### If Database Connection Fails:
```bash
# Start database container
docker-compose up -d db

# Wait 10 seconds, then try again
```

### If Port 8000 is Busy:
```bash
# Use different port
python manage.py runserver 0.0.0.0:8001
```

## ✅ Benefits

1. **No Docker overhead** - Faster startup
2. **Single server** - No duplicate issues
3. **Easy debugging** - Full IDE support
4. **Direct code access** - Instant changes

## 🛑 To Stop

Press `Ctrl+C` in the terminal where server is running.

