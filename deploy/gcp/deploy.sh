#!/usr/bin/env bash
# deploy.sh — Deploy EventFlow backend to a GCE VM using pre-built images.
#
# This script is an alternative to the GitHub Actions deploy workflow.
# It pulls the latest image from Artifact Registry on the VM and restarts.
#
# Prerequisites:
#   - VM provisioned (run provision-vm.sh or terraform apply)
#   - Docker image pushed to Artifact Registry (run CI or build locally)
#   - gcloud CLI authenticated with appropriate permissions
#
# Configure via environment variables:
#   PROJECT_ID       GCP project id (defaults to current gcloud config)
#   ZONE             GCE zone (default: us-central1-a)
#   INSTANCE         VM name (default: eventflow-api)
#   REMOTE_DIR       Remote install path (default: /opt/eventflow)
#   IMAGE_TAG        Full Artifact Registry image tag (default: builds locally)
#   API_PORT         Health check port (default: 8000)
#
# Usage:
#   bash deploy/gcp/deploy.sh
#   SKIP_MIGRATE=1 bash deploy/gcp/deploy.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE="${INSTANCE:-eventflow-api}"
REMOTE_DIR="${REMOTE_DIR:-/opt/eventflow}"
API_PORT="${API_PORT:-8000}"

REGION="${ZONE%-*}"
DEFAULT_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/eventflow/api:latest"
IMAGE_TAG="${IMAGE_TAG:-${DEFAULT_TAG}}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no PROJECT_ID set and no default gcloud project configured." >&2
  exit 1
fi

GCLOUD=(gcloud --project "${PROJECT_ID}")

remote() {
  "${GCLOUD[@]}" compute ssh "${INSTANCE}" --zone "${ZONE}" --quiet --command "$1"
}

echo "==> Waiting for SSH on '${INSTANCE}'…"
SSH_OK=0
for i in $(seq 1 30); do
  if remote "echo ok" >/dev/null 2>&1; then
    SSH_OK=1
    break
  fi
  sleep 6
done
if [[ "${SSH_OK}" != "1" ]]; then
  echo "ERROR: SSH never became reachable." >&2
  exit 1
fi

echo "==> Ensuring ${REMOTE_DIR} exists…"
remote "sudo mkdir -p ${REMOTE_DIR} && sudo chown -R \$(id -u):\$(id -g) ${REMOTE_DIR}"

echo "==> Uploading docker-compose.yml + Caddyfile + prometheus.yml + grafana/…"
tar -czf - \
  --exclude='./.git' \
  --exclude='./node_modules' \
  --exclude='./apps' \
  --exclude='./.venv' \
  --exclude='./venv' \
  --exclude='./eventflow' \
  --exclude='./migrations' \
  --exclude='./tests' \
  --exclude='./scripts' \
  docker-compose.yml \
  Caddyfile \
  prometheus.yml \
  grafana/ \
  deploy/ \
  | remote "set -e; \
    STAGE=\"/tmp/eventflow.stage.\$\$\"; \
    rm -rf \"\$STAGE\"; \
    mkdir -p \"\$STAGE\"; \
    tar -xzf - -C \"\$STAGE\"; \
    sudo rsync -a --delete \
      --exclude='.env' \
      --exclude='eventflow/' \
      --exclude='migrations/' \
      \"\$STAGE/\" \"${REMOTE_DIR}/\"; \
    rm -rf \"\$STAGE\""

# The source code dirs are uploaded separately to minimize upload time on redeploy
# (docker-compose.yml changes infrequently, source code changes every commit).
# For a full deploy (first time or after source changes), also upload the app code.
if [[ -z "${SKIP_CODE_UPLOAD:-}" ]]; then
  echo "==> Uploading application code…"
  tar -czf - \
    --exclude='./__pycache__' \
    --exclude='./**/__pycache__' \
    eventflow/ \
    migrations/ \
    alembic.ini \
    pyproject.toml \
    .env.example \
    | remote "sudo tar -xzf - -C ${REMOTE_DIR}"
fi

echo "==> Pulling image ${IMAGE_TAG} and starting stack…"
remote "cd ${REMOTE_DIR} && \
  export IMAGE_TAG=${IMAGE_TAG} && \
  sudo docker compose pull && \
  sudo docker compose up -d --remove-orphans"

echo "==> Waiting for api container to be ready…"
remote "cd ${REMOTE_DIR} && \
  for i in \$(seq 1 30); do
    sudo docker compose ps --status running api 2>/dev/null | grep -q api && break || true
    sleep 2
  done"

echo "==> Running database migrations…"
if [[ -z "${SKIP_MIGRATE:-}" ]]; then
  remote "cd ${REMOTE_DIR} && \
    for i in \$(seq 1 5); do
      sudo docker compose exec -T api alembic upgrade head && exit 0
      echo 'alembic attempt '\$i' failed, retrying in 5s…'
      sleep 5
    done
    echo 'alembic upgrade head failed' >&2; exit 1"
fi

echo "==> Health check…"
EXTERNAL_IP="$("${GCLOUD[@]}" compute instances describe "${INSTANCE}" --zone "${ZONE}" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"

for i in $(seq 1 12); do
  if curl -fsS --max-time 3 "http://${EXTERNAL_IP}:${API_PORT}/api/v1/healthz" >/dev/null; then
    echo "✓ API healthy at http://${EXTERNAL_IP}:${API_PORT}/api/v1/healthz"
    exit 0
  fi
  sleep 5
done

echo "WARN: health check did not pass. Inspect with:" >&2
echo "  gcloud compute ssh ${INSTANCE} --zone ${ZONE} --command 'cd ${REMOTE_DIR} && sudo docker compose logs --tail=200 api'" >&2
exit 1
