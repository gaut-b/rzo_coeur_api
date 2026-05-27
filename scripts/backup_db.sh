#!/bin/bash
# Backup PostgreSQL database using pg_dump inside the Docker container.
# Reads .env from the parent folder and stores backups in
# /opt/backups/<parent-folder-name>/.
# Creates compressed dumps with timestamp, retains only the last 7 days.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$BASE_DIR/docker-compose.prod.yml"
ENV_FILE="$BASE_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "No .env file found in $BASE_DIR"
  exit 1
fi

BACKUP_DIR="/opt/backups/$(basename "$BASE_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=7

# Load environment variables from .env file
# Export only SQL_DATABASE and SQL_USER to avoid overriding system variables
export $(grep -E '^(SQL_DATABASE|SQL_USER)=' "$ENV_FILE" | xargs)

DB_NAME="${SQL_DATABASE:?ERROR: SQL_DATABASE is not set in .env}"
DB_USER="${SQL_USER:?ERROR: SQL_USER is not set in .env}"
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backing up database ${DB_NAME}..."

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

find "$BACKUP_DIR" -name "backup_*.sql.gz" \
  -mtime "+${RETENTION_DAYS}" -delete

echo "[$(date)] Backup saved to ${BACKUP_FILE}"
