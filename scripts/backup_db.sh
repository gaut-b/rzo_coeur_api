#!/bin/bash
# Backup PostgreSQL database using pg_dump inside the Docker container.
# Creates compressed dumps with timestamp, retains only the last 7 days.

set -e

BACKUP_DIR="/opt/backups/postgres"
COMPOSE_FILE="/opt/rzo_coeur_api/docker-compose.prod.yml"
ENV_FILE="/opt/rzo_coeur_api/.env"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=7

# Load environment variables from .env file
if [ -f "$ENV_FILE" ]; then
    # Export only SQL_DATABASE and SQL_USER to avoid overriding system variables
    export $(grep -E '^(SQL_DATABASE|SQL_USER)=' "$ENV_FILE" | xargs)
else
    echo "[$(date)] ERROR: .env file not found at ${ENV_FILE}"
    exit 1
fi

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
