#!/bin/bash
scp docker-compose.prod.yml vps:/opt/rzo_coeur_api/
scp webhook/hooks.json vps:/opt/rzo_coeur_api/webhook/
scp scripts/deploy.sh vps:/opt/rzo_coeur_api/scripts/
scp scripts/backup_db.sh vps:/opt/rzo_coeur_api/scripts/
