#!/bin/bash
# HMS Automated Backup Script
# Backs up PostgreSQL database and media files

BACKUP_DIR="/var/backups/hms"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

echo "🔄 Starting HMS backup - $DATE"

# Backup PostgreSQL database
echo "💾 Backing up database..."
sudo -u postgres pg_dump hms_production | gzip > $BACKUP_DIR/hms_db_$DATE.sql.gz
if [ $? -eq 0 ]; then
    echo "   ✅ Database backup complete"
else
    echo "   ❌ Database backup failed!"
    exit 1
fi

# Backup media files
echo "📁 Backing up media files..."
tar -czf $BACKUP_DIR/hms_media_$DATE.tar.gz /var/www/hms/media/ 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Media backup complete"
else
    echo "   ⚠️  Media backup warning (may be empty)"
fi

# Backup static files (optional)
echo "📦 Backing up static files..."
tar -czf $BACKUP_DIR/hms_static_$DATE.tar.gz /var/www/hms/staticfiles/ 2>/dev/null

# Delete old backups
echo "🧹 Cleaning old backups (older than $KEEP_DAYS days)..."
find $BACKUP_DIR -name "hms_db_*.sql.gz" -type f -mtime +$KEEP_DAYS -delete
find $BACKUP_DIR -name "hms_media_*.tar.gz" -type f -mtime +$KEEP_DAYS -delete
find $BACKUP_DIR -name "hms_static_*.tar.gz" -type f -mtime +$KEEP_DAYS -delete

# Get backup sizes
DB_SIZE=$(du -h $BACKUP_DIR/hms_db_$DATE.sql.gz | cut -f1)
MEDIA_SIZE=$(du -h $BACKUP_DIR/hms_media_$DATE.tar.gz 2>/dev/null | cut -f1)

echo ""
echo "✅ Backup completed successfully!"
echo "   Database: $DB_SIZE"
echo "   Media: $MEDIA_SIZE"
echo "   Location: $BACKUP_DIR"
echo "   Date: $DATE"
echo ""

# Optional: Upload to remote storage (uncomment if using)
# rsync -avz $BACKUP_DIR/ user@backup-server:/backups/hms/
# aws s3 sync $BACKUP_DIR s3://your-bucket/hms-backups/

















