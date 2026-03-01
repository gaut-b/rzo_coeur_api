#!/bin/bash
# Deploy script triggered by webhook.
# Pulls the latest Docker image and restarts the backend service.

set -e

# Use the deploy user's Docker credentials even when running as root/sudo
export DOCKER_CONFIG=/home/deploy/.docker

COMPOSE_FILE="/opt/rzo_coeur_api/docker-compose.prod.yml"
REGISTRY="ghcr.io"
IMAGE="ghcr.io/gaut-b/rzo_coeur_api"

echo "[$(date)] Starting deployment..."

cd /opt/rzo_coeur_api

# Backup database before deploying
/opt/rzo_coeur_api/scripts/backup_db.sh

# Pull the latest images from GHCR (backend + nginx + webhook)
docker compose -f "$COMPOSE_FILE" pull backend nginx webhook

# Restart backend, nginx and webhook — db is untouched
docker compose -f "$COMPOSE_FILE" up -d \
  --no-deps \
  --force-recreate \
  backend nginx webhook

# Apply any pending migrations
docker compose -f "$COMPOSE_FILE" exec -T backend \
  python manage.py migrate

# Remove unused images to free disk space
docker image prune -f

echo "[$(date)] Deployment complete."
