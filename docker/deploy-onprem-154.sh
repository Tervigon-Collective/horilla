#!/usr/bin/env bash
# Deploy Horilla app + media/static to 132.154.65.28 (port 8002).
# Database stays on DB_HOST (default 72.61.228.168) — no pg_dump/restore.
set -euo pipefail

DEST_HOST="${DEST_HOST:-132.154.65.28}"
DEST_SSH_PORT="${DEST_SSH_PORT:-2222}"
DEST_USER="${DEST_USER:-root}"
SSH_KEY="${SSH_KEY:-/root/.ssh/id_ed25519_132}"
APP_PORT="${APP_PORT:-8002}"
SOURCE_APP_DIR="${SOURCE_APP_DIR:-/var/jenkins_apps/horilla}"
SOURCE_SRC_DIR="${SOURCE_SRC_DIR:-/var/jenkins_apps/horilla-src}"
IMAGE="${IMAGE:-horilla_app:latest}"
CONTAINER="${CONTAINER:-horilla-app-onprem}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/var/jenkins_apps/horilla}"

SSH=(ssh -i "$SSH_KEY" -p "$DEST_SSH_PORT" -o StrictHostKeyChecking=no "${DEST_USER}@${DEST_HOST}")
RSYNC=(rsync -avz -e "ssh -i $SSH_KEY -p $DEST_SSH_PORT -o StrictHostKeyChecking=no")

echo "=== Pre-flight: free port ${APP_PORT} on ${DEST_HOST} ==="
"${SSH[@]}" "for p in ${APP_PORT}; do ss -tln | grep -q \":\$p \" && echo TAKEN:\$p && exit 1 || echo FREE:\$p; done"

echo "=== Ensure remote directories ==="
"${SSH[@]}" "mkdir -p ${REMOTE_APP_DIR}/{logs,media,staticfiles,backups}"

echo "=== Sync media + staticfiles (data, not DB) ==="
"${RSYNC[@]}" "${SOURCE_APP_DIR}/media/" "${DEST_USER}@${DEST_HOST}:${REMOTE_APP_DIR}/media/"
"${RSYNC[@]}" "${SOURCE_APP_DIR}/staticfiles/" "${DEST_USER}@${DEST_HOST}:${REMOTE_APP_DIR}/staticfiles/"

echo "=== Build + export image on source ==="
docker build -t "$IMAGE" "$SOURCE_SRC_DIR"
docker save "$IMAGE" | gzip | "${SSH[@]}" "gunzip | docker load"

echo "=== Copy env (create from example on first run) ==="
if [[ -f ${SOURCE_APP_DIR}/.env.onprem-154 ]]; then
  "${RSYNC[@]}" "${SOURCE_APP_DIR}/.env.onprem-154" "${DEST_USER}@${DEST_HOST}:${REMOTE_APP_DIR}/.env"
else
  echo "WARN: ${SOURCE_APP_DIR}/.env.onprem-154 missing — copy docker/.env.onprem-154.example and set secrets on dest"
fi

echo "=== Start container on port ${APP_PORT} ==="
"${SSH[@]}" bash -s <<EOF
set -e
docker rm -f ${CONTAINER} 2>/dev/null || true
docker run -d \\
  --name ${CONTAINER} \\
  --restart unless-stopped \\
  --env-file ${REMOTE_APP_DIR}/.env \\
  --log-opt max-size=10m \\
  --log-opt max-file=3 \\
  -p ${APP_PORT}:8000 \\
  -v ${REMOTE_APP_DIR}/logs:/app/logs \\
  -v ${REMOTE_APP_DIR}/media:/app/media \\
  -v ${REMOTE_APP_DIR}/staticfiles:/app/staticfiles \\
  ${IMAGE}
for i in \$(seq 1 30); do
  curl -fsS --max-time 5 http://127.0.0.1:${APP_PORT}/login/ >/dev/null && echo healthy && exit 0
  sleep 3
done
docker logs --tail 50 ${CONTAINER}
exit 1
EOF

echo "=== Done: http://${DEST_HOST}:${APP_PORT}/login/ ==="
