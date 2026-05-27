#!/bin/bash
# Copy configuration files to a VPS environment folder.
# Usage: update_vps_conf_files.sh <folder>
# Example: update_vps_conf_files.sh rzo_coeur_api
#          update_vps_conf_files.sh rzo_coeur_staging

FOLDER="${1:?Usage: $0 <folder>}"
REMOTE_DIR="vps:/opt/${FOLDER}"

scp docker-compose.prod.yml "$REMOTE_DIR/"
scp scripts/deploy.sh "$REMOTE_DIR/scripts/"
scp scripts/backup_db.sh "$REMOTE_DIR/scripts/"
