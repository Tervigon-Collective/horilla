#!/usr/bin/env bash
# Deploy Horilla to on-prem 132.154.65.28 (127.0.0.1:18083 via docker compose).
# Database stays on DB_HOST (default 72.61.228.168) — no pg_dump/restore.
# Does not depend on /var/jenkins_apps/horilla (retired on 168).
set -euo pipefail

DEST_HOST="${DEST_HOST:-132.154.65.28}"
DEST_SSH_PORT="${DEST_SSH_PORT:-2222}"
DEST_USER="${DEST_USER:-tervigon}"
SSH_KEY="${SSH_KEY:-/root/.ssh/id_ed25519_132}"
SOURCE_SRC_DIR="${SOURCE_SRC_DIR:-.}"
IMAGE="${IMAGE:-horilla_app:latest}"
REMOTE_HRMS_ROOT="${REMOTE_HRMS_ROOT:-/srv/seleric/hrms}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-${REMOTE_HRMS_ROOT}/horilla}"
ENV_SOURCE="${ENV_SOURCE:-}"

SSH=(ssh -i "$SSH_KEY" -p "$DEST_SSH_PORT" -o StrictHostKeyChecking=no "${DEST_USER}@${DEST_HOST}")
RSYNC=(rsync -avz --delete
  --exclude .git
  --exclude .github/
  --exclude '**/tests/'
  --exclude media/
  --exclude staticfiles/
  --exclude logs/
  --exclude __pycache__/
  --exclude '*.pyc'
  -e "ssh -i $SSH_KEY -p $DEST_SSH_PORT -o StrictHostKeyChecking=no")

echo "=== Pre-flight: HRMS port 18083 on ${DEST_HOST} ==="
"${SSH[@]}" "ss -tln | grep -q ':18083 ' && echo LISTEN:18083 || echo FREE:18083"

echo "=== Ensure remote app directories (preserve media/static) ==="
"${SSH[@]}" "mkdir -p ${REMOTE_APP_DIR}/{logs,media,staticfiles}"

echo "=== Sync application source (code only; media/static stay on dest) ==="
"${RSYNC[@]}" "${SOURCE_SRC_DIR}/" "${DEST_USER}@${DEST_HOST}:${REMOTE_APP_DIR}/"

echo "=== Build + export image on Jenkins host ==="
docker build -t "$IMAGE" "${SOURCE_SRC_DIR}"
docker save "$IMAGE" | gzip | "${SSH[@]}" "gunzip | docker load"

echo "=== Ensure .env on dest ==="
"${SSH[@]}" bash -s <<EOF
set -e
test -f ${REMOTE_APP_DIR}/.env || { echo "FAIL: missing ${REMOTE_APP_DIR}/.env on on-prem — create it once on 154"; exit 1; }
EOF
if [[ -n "${ENV_SOURCE:-}" && -f "${ENV_SOURCE}" ]]; then
  "${SSH[@]}" "test -f ${REMOTE_APP_DIR}/.env || cp ${ENV_SOURCE} ${REMOTE_APP_DIR}/.env"
fi

echo "=== Restart via on-prem compose (127.0.0.1:18083) ==="
"${SSH[@]}" "HRMS_APP_ONLY=1 bash ${REMOTE_HRMS_ROOT}/deploy-hrms.sh"

echo "=== Health check ==="
"${SSH[@]}" bash -s <<'EOF'
for i in $(seq 1 40); do
  curl -fsS --max-time 8 http://127.0.0.1:18083/login/ >/dev/null && echo healthy && exit 0
  sleep 5
done
docker logs --tail 80 horilla-web-1 2>/dev/null || docker compose -f /srv/seleric/hrms/horilla/docker-compose.server.yml ps
exit 1
EOF

echo "=== Done: https://hrms.seleric.com/login/ ==="
