#!/bin/bash
# Deploy script — pulls the latest images and restarts the services.
# Works for both prod and staging: auto-detects the compose file
# from the folder it lives in.

set -e

# Use the deploy user's Docker credentials even when running as root/sudo
export DOCKER_CONFIG=/home/deploy/.docker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$BASE_DIR/docker-compose.prod.yml"

REGISTRY="ghcr.io"
IMAGE="ghcr.io/gaut-b/rzo_coeur_api"

echo "[$(date)] Starting deployment from $BASE_DIR..."

cd "$BASE_DIR"

# Backup database before deploying
"$SCRIPT_DIR/backup_db.sh"

# Pull the latest images from GHCR (backend + nginx)
docker compose -f "$COMPOSE_FILE" pull backend nginx

# Ensure db and minio are running (no-op if already up)
docker compose -f "$COMPOSE_FILE" up -d db minio

# Restart backend and nginx — db/minio are untouched
docker compose -f "$COMPOSE_FILE" up -d \
  --no-deps \
  --force-recreate \
  backend nginx

# Apply any pending migrations
docker compose -f "$COMPOSE_FILE" exec -T backend \
  python manage.py migrate

# Remove unused images to free disk space
docker image prune -f

echo "[$(date)] Deployment complete."
