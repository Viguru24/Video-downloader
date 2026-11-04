#!/bin/bash
# OmniDownloader SQLite & Configuration GFS Backup Script

# Configuration
APP_DIR="/opt/omni-downloader"
DB_PATH="$APP_DIR/downloads.db"
CONFIG_PATH="$APP_DIR/config.json"
BACKUP_DIR="/root/backups/omni-downloader"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
FILENAME="omni_downloader_backup_$TIMESTAMP.tar.gz"
STATUS_FILE="$APP_DIR/backup_status.json"

# Create backup directories if they do not exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$APP_DIR"

echo "[$(date)] Starting OmniDownloader GFS Backup..."

if [ ! -f "$DB_PATH" ]; then
    echo "?? Database not found at $DB_PATH, initializing empty DB..."
    touch "$DB_PATH"
fi

# 1. Atomic Local SQLite Backup to temporary file
TEMP_DIR=$(mktemp -d)
TEMP_DB="$TEMP_DIR/downloads.db"

echo "[$(date)] Performing atomic SQLite backup..."
sqlite3 "$DB_PATH" ".backup '$TEMP_DB'" 2>/dev/null
if [ $? -ne 0 ] || [ ! -s "$TEMP_DB" ]; then
    echo "?? sqlite3 .backup command returned non-zero, falling back to copy..."
    cp "$DB_PATH" "$TEMP_DB"
fi

# 2. Stage files into a clean archive directory
ARCHIVE_STAGE="$TEMP_DIR/omni_archive"
mkdir -p "$ARCHIVE_STAGE"
cp "$TEMP_DB" "$ARCHIVE_STAGE/downloads.db"

# Copy config if exists
if [ -f "$CONFIG_PATH" ]; then
    cp "$CONFIG_PATH" "$ARCHIVE_STAGE/config.json"
fi

# Write metadata manifest into archive
cat <<EOF > "$ARCHIVE_STAGE/backup_manifest.json"
{
  "project": "omni-downloader",
  "timestamp": "$TIMESTAMP",
  "db_size": $(stat -c%s "$TEMP_DB" 2>/dev/null || echo 0),
  "db_path": "$DB_PATH"
}
EOF

# 3. Create compressed tar.gz archive
tar -czf "$BACKUP_DIR/$FILENAME" -C "$ARCHIVE_STAGE" .
ARCHIVE_EXIT=$?

# Clean up temp working dir
rm -rf "$TEMP_DIR"

if [ $ARCHIVE_EXIT -eq 0 ]; then
    echo "[?] $(date) Local backup successful: $FILENAME"
    
    # 4. Stage into Local GFS Rotation Vault
    echo "[$(date)] Staging to Local GFS Vault..."
    DAILY_DIR="$BACKUP_DIR/daily"
    WEEKLY_DIR="$BACKUP_DIR/weekly"
    MONTHLY_DIR="$BACKUP_DIR/monthly"

    mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR"

    # Always vault to Daily (Son) - Keep 7 days
    cp "$BACKUP_DIR/$FILENAME" "$DAILY_DIR/"
    find "$DAILY_DIR" -type f -name "omni_downloader_backup_*.tar.gz" -mtime +7 -delete

    # Weekly (Father) - Sundays - Keep 28 days
    if [ $(date +%u) -eq 7 ]; then
        echo "[$(date)] Sunday detected. Staging Weekly backup..."
        cp "$BACKUP_DIR/$FILENAME" "$WEEKLY_DIR/"
        find "$WEEKLY_DIR" -type f -name "omni_downloader_backup_*.tar.gz" -mtime +28 -delete
    fi

    # Monthly (Grandfather) - 1st of month - Keep 365 days
    if [ $(date +%d) -eq "01" ]; then
        echo "[$(date)] 1st of month detected. Staging Monthly backup..."
        cp "$BACKUP_DIR/$FILENAME" "$MONTHLY_DIR/"
        find "$MONTHLY_DIR" -type f -name "omni_downloader_backup_*.tar.gz" -mtime +365 -delete
    fi

    # Optional: If rclone gdrive is configured for root, vault to Google Drive
    if rclone listremotes 2>/dev/null | grep -q "^gdrive:"; then
        echo "[$(date)] Vaulting to Google Drive..."
        rclone copy "$BACKUP_DIR/$FILENAME" gdrive:Backups/OmniDownloader/Daily --quiet 2>/dev/null || true
    fi

    # 5. Clean up root backup folder older than 3 days (already safely staged in GFS)
    find "$BACKUP_DIR" -maxdepth 1 -name "omni_downloader_backup_*.tar.gz" -mtime +3 -delete

    echo "[?] $(date) Local GFS Vaulting completed successfully."
    echo "{\"status\": \"SUCCESS\", \"last_run\": \"$TIMESTAMP\", \"file\": \"$FILENAME\", \"archive\": \"VAULTED\"}" > "$STATUS_FILE"
    chmod 666 "$STATUS_FILE" 2>/dev/null || true
else
    echo "? $(date) Archive FAILED!"
    echo "{\"status\": \"FAILED\", \"last_run\": \"$TIMESTAMP\"}" > "$STATUS_FILE"
    exit 1
fi
