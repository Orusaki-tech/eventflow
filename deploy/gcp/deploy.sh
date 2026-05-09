#!/usr/bin/env bash
# deploy.sh — push the EventFlow backend to a GCP VM and (re)start the stack.
#
# Idempotent. Uploads the working tree (minus venv/.git/secrets) to
# /opt/eventflow on the VM, copies the local production env file into place,
# then runs `docker compose up -d --build`, applies Alembic migrations, and
# (optionally) installs the systemd unit so the stack comes back on reboot.
#
# Required:
#   - The VM must already exist (run `deploy/gcp/provision-vm.sh` first).
#   - A local env file with prod secrets (default: deploy/gcp/.env.production).
#     See deploy/gcp/.env.production.example.
#
# Configure via environment variables:
#   PROJECT_ID       GCP project id (defaults to current `gcloud config`)
#   ZONE             GCE zone (default: us-central1-a)
#   INSTANCE         VM name (default: eventflow-api)
#   REMOTE_DIR       Remote install path (default: /opt/eventflow)
#   ENV_FILE         Local env file to copy as remote .env
#                    (default: deploy/gcp/.env.production)
#   INSTALL_SYSTEMD  "1" to (re)install systemd unit (default: 1)
#   SKIP_BUILD       "1" to `docker compose up -d` without rebuilding (default: 0)
#   API_PORT         Health check port (default: 8000)
#
# Usage:
#   bash deploy/gcp/deploy.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE="${INSTANCE:-eventflow-api}"
REMOTE_DIR="${REMOTE_DIR:-/opt/eventflow}"
ENV_FILE="${ENV_FILE:-deploy/gcp/.env.production}"
INSTALL_SYSTEMD="${INSTALL_SYSTEMD:-1}"
SKIP_BUILD="${SKIP_BUILD:-0}"
API_PORT="${API_PORT:-8000}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no PROJECT_ID set and no default gcloud project configured." >&2
  echo "       Run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: env file '${ENV_FILE}' not found." >&2
  echo "       Copy deploy/gcp/.env.production.example and fill it in." >&2
  exit 1
fi

GCLOUD=(gcloud --project "${PROJECT_ID}")

remote() {
  "${GCLOUD[@]}" compute ssh "${INSTANCE}" --zone "${ZONE}" --quiet --command "$1"
}

remote_stdin() {
  "${GCLOUD[@]}" compute ssh "${INSTANCE}" --zone "${ZONE}" --quiet --command "$1"
}

echo "==> Waiting for SSH on '${INSTANCE}' (up to ~3 min)…"
# Fresh GCE VMs need 30–90s before sshd accepts connections. Retry quietly
# instead of failing on the first "Connection refused".
SSH_OK=0
for i in $(seq 1 30); do
  if remote "echo ok" >/dev/null 2>&1; then
    SSH_OK=1
    break
  fi
  sleep 6
done
if [[ "${SSH_OK}" != "1" ]]; then
  echo "ERROR: SSH never became reachable on '${INSTANCE}'." >&2
  echo "       Check console: gcloud compute instances describe ${INSTANCE} --zone ${ZONE}" >&2
  exit 1
fi

echo "==> Waiting for Docker + Compose plugin (startup script installs them; up to ~5 min)…"
# The provision-vm.sh startup script installs Docker on first boot. On a small
# VM that can take 2–5 minutes after sshd comes up. Retry the docker check.
DOCKER_OK=0
for i in $(seq 1 30); do
  if remote "command -v docker >/dev/null && docker compose version >/dev/null" 2>/dev/null; then
    DOCKER_OK=1
    break
  fi
  sleep 10
done
if [[ "${DOCKER_OK}" != "1" ]]; then
  echo "ERROR: Docker / Compose plugin not ready on the VM after ~5 min." >&2
  echo "       Inspect startup-script logs:" >&2
  echo "         gcloud compute ssh ${INSTANCE} --zone ${ZONE} \\" >&2
  echo "           --command 'sudo journalctl -u google-startup-scripts.service --no-pager | tail -100'" >&2
  exit 1
fi

echo "==> Ensuring ${REMOTE_DIR} exists and is writable by the deploy user…"
remote "sudo mkdir -p ${REMOTE_DIR} && sudo chown -R \$(id -u):\$(id -g) ${REMOTE_DIR}"

# Build a tar of the working tree (excluding bulky/secret paths) and stream it
# over `gcloud compute ssh` into the remote. Using a staging dir + atomic
# rsync-into-place means we never leave the remote in a half-updated state.
echo "==> Uploading source to ${INSTANCE}:${REMOTE_DIR} (tar over SSH)…"
TAR_EXCLUDES=(
  --exclude='./.git'
  --exclude='./.venv'
  --exclude='./venv'
  --exclude='./venv.*'
  --exclude='./__pycache__'
  --exclude='./**/__pycache__'
  --exclude='./.pytest_cache'
  --exclude='./.mypy_cache'
  --exclude='./.ruff_cache'
  --exclude='./node_modules'
  --exclude='./apps/mobile/.expo'
  --exclude='./apps/mobile/node_modules'
  --exclude='./data'
  --exclude='./*.sqlite'
  --exclude='./*.sqlite3'
  --exclude='./.env'
  --exclude='./.env.*'
  --exclude='./deploy/gcp/.env.production'
  --exclude='./.DS_Store'
)

tar -czf - "${TAR_EXCLUDES[@]}" -C "${REPO_ROOT}" . \
  | remote "set -e; \
      STAGE=\"/tmp/eventflow.stage.\$\$\"; \
      rm -rf \"\$STAGE\"; \
      mkdir -p \"\$STAGE\"; \
      tar -xzf - -C \"\$STAGE\"; \
      sudo apt-get install -y rsync >/dev/null 2>&1 || true; \
      sudo rsync -a --delete \
        --exclude='.env' \
        \"\$STAGE/\" \"${REMOTE_DIR}/\"; \
      rm -rf \"\$STAGE\""

echo "==> Uploading env file (${ENV_FILE} → ${REMOTE_DIR}/.env)…"
"${GCLOUD[@]}" compute scp --zone "${ZONE}" --quiet \
  "${ENV_FILE}" "${INSTANCE}:/tmp/eventflow.env"
remote "sudo install -m 600 -o root -g root /tmp/eventflow.env ${REMOTE_DIR}/.env && rm -f /tmp/eventflow.env"

if [[ "${SKIP_BUILD}" == "1" ]]; then
  COMPOSE_UP="sudo docker compose --env-file .env up -d --remove-orphans"
else
  COMPOSE_UP="sudo docker compose --env-file .env up -d --build --remove-orphans"
fi

echo "==> Starting stack on the VM…"
remote "cd ${REMOTE_DIR} && ${COMPOSE_UP}"

echo "==> Waiting for the api container to be ready…"
# We're DB-agnostic here: DB_URL points at Supabase / Cloud SQL / etc. The api
# container is the source of truth — once it can reach its DB, alembic can run.
remote "cd ${REMOTE_DIR} && for i in \$(seq 1 30); do sudo docker compose ps --status running api 2>/dev/null | grep -q api && exit 0; sleep 2; done; echo 'api container never reached running state' >&2; exit 1"

echo "==> Running database migrations (alembic upgrade head)…"
# Retries because Supabase pooler DNS / connection setup can take a few seconds
# the first time the container starts.
remote "cd ${REMOTE_DIR} && for i in \$(seq 1 5); do sudo docker compose exec -T api alembic upgrade head && exit 0; echo 'alembic attempt '\$i' failed, retrying in 5s…'; sleep 5; done; echo 'alembic upgrade head failed after 5 attempts' >&2; exit 1"

if [[ "${INSTALL_SYSTEMD}" == "1" ]]; then
  echo "==> Installing systemd unit so the stack starts on boot…"
  remote "sudo cp ${REMOTE_DIR}/deploy/systemd/eventflow.service /etc/systemd/system/eventflow.service && sudo systemctl daemon-reload && sudo systemctl enable eventflow.service"
fi

echo "==> Health check…"
EXTERNAL_IP="$("${GCLOUD[@]}" compute instances describe "${INSTANCE}" --zone "${ZONE}" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"

set +e
for i in $(seq 1 20); do
  if curl -fsS --max-time 3 "http://${EXTERNAL_IP}:${API_PORT}/api/v1/healthz" >/dev/null; then
    echo "✓ API healthy at http://${EXTERNAL_IP}:${API_PORT}/api/v1/healthz"
    MOBILE_ENV_FILE="${REPO_ROOT}/apps/mobile/.env.deployment"
    GENERATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    cat >"${MOBILE_ENV_FILE}" <<EOF
# Generated by deploy/gcp/deploy.sh at ${GENERATED_AT}
# Loaded by apps/mobile/app.config.ts when EXPO_PUBLIC_EVENTFLOW_API_URL is not set.
# Override anytime in .env.local with EXPO_PUBLIC_EVENTFLOW_API_URL=...
EXPO_PUBLIC_EVENTFLOW_API_URL=http://${EXTERNAL_IP}:${API_PORT}
EOF
    echo "==> Wrote ${MOBILE_ENV_FILE} — restart Expo (Metro) so the app picks up the API URL."
    exit 0
  fi
  sleep 3
done
set -e

echo "WARN: health check did not pass after ~60s. Inspect logs with:" >&2
echo "  gcloud --project ${PROJECT_ID} compute ssh ${INSTANCE} --zone ${ZONE} \\" >&2
echo "    --command 'cd ${REMOTE_DIR} && sudo docker compose logs --tail=200 api'" >&2
exit 1
