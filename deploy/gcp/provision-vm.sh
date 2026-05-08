#!/usr/bin/env bash
# provision-vm.sh — one-time GCP VM provisioning for EventFlow.
#
# Creates a Debian 12 VM with Docker + Compose plugin pre-installed via a
# startup script, opens TCP :8000 to the world, and reserves a static
# external IP so the VM keeps the same address across reboots.
#
# Re-running this script is safe: it skips resources that already exist.
#
# Required:
#   - `gcloud` CLI authenticated (`gcloud auth login`) and a default project set
#     (`gcloud config set project <PROJECT_ID>`), OR pass PROJECT_ID below.
#
# Configure via environment variables (all optional, sensible defaults):
#   PROJECT_ID    GCP project id (defaults to current `gcloud config`)
#   ZONE          GCE zone (default: us-central1-a)
#   REGION        GCE region (default: derived from ZONE)
#   INSTANCE      VM name (default: eventflow-api)
#   MACHINE_TYPE  GCE machine type (default: e2-small)
#   DISK_SIZE_GB  Boot disk size (default: 30)
#   IMAGE_FAMILY  GCE image family (default: debian-12)
#   IMAGE_PROJECT GCE image project (default: debian-cloud)
#   STATIC_IP     Static IP address name (default: eventflow-api-ip)
#   FW_RULE       Firewall rule name for :8000 (default: eventflow-allow-api)
#   API_PORT      Port to open (default: 8000)
#
# Usage:
#   bash deploy/gcp/provision-vm.sh
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
ZONE="${ZONE:-us-central1-a}"
REGION="${REGION:-${ZONE%-*}}"
INSTANCE="${INSTANCE:-eventflow-api}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-small}"
DISK_SIZE_GB="${DISK_SIZE_GB:-30}"
IMAGE_FAMILY="${IMAGE_FAMILY:-debian-12}"
IMAGE_PROJECT="${IMAGE_PROJECT:-debian-cloud}"
STATIC_IP="${STATIC_IP:-eventflow-api-ip}"
FW_RULE="${FW_RULE:-eventflow-allow-api}"
API_PORT="${API_PORT:-8000}"
NETWORK_TAG="eventflow-api"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no PROJECT_ID set and no default gcloud project configured." >&2
  echo "       Run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

echo "==> Project: ${PROJECT_ID}"
echo "==> Region:  ${REGION}"
echo "==> Zone:    ${ZONE}"
echo "==> VM:      ${INSTANCE} (${MACHINE_TYPE}, ${DISK_SIZE_GB}GB)"

GCLOUD=(gcloud --project "${PROJECT_ID}")

echo "==> Enabling required services (compute, iam)…"
"${GCLOUD[@]}" services enable compute.googleapis.com iam.googleapis.com >/dev/null

# ---------- Static external IP ----------
if "${GCLOUD[@]}" compute addresses describe "${STATIC_IP}" --region "${REGION}" >/dev/null 2>&1; then
  echo "==> Static IP '${STATIC_IP}' already exists, reusing."
else
  echo "==> Reserving static IP '${STATIC_IP}'…"
  "${GCLOUD[@]}" compute addresses create "${STATIC_IP}" --region "${REGION}"
fi
EXTERNAL_IP="$("${GCLOUD[@]}" compute addresses describe "${STATIC_IP}" --region "${REGION}" --format='value(address)')"
echo "==> External IP: ${EXTERNAL_IP}"

# ---------- Firewall rule for API port ----------
if "${GCLOUD[@]}" compute firewall-rules describe "${FW_RULE}" >/dev/null 2>&1; then
  echo "==> Firewall rule '${FW_RULE}' already exists, reusing."
else
  echo "==> Creating firewall rule '${FW_RULE}' (TCP :${API_PORT}, tag=${NETWORK_TAG})…"
  "${GCLOUD[@]}" compute firewall-rules create "${FW_RULE}" \
    --direction=INGRESS \
    --action=ALLOW \
    --rules="tcp:${API_PORT}" \
    --source-ranges="0.0.0.0/0" \
    --target-tags="${NETWORK_TAG}"
fi

# ---------- Startup script (installs Docker + Compose plugin) ----------
STARTUP_SCRIPT="$(cat <<'STARTUP'
#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg rsync
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi
mkdir -p /opt/eventflow
chown -R "$(id -un 1000 2>/dev/null || echo root):$(id -gn 1000 2>/dev/null || echo root)" /opt/eventflow || true
STARTUP
)"

# ---------- VM ----------
if "${GCLOUD[@]}" compute instances describe "${INSTANCE}" --zone "${ZONE}" >/dev/null 2>&1; then
  echo "==> VM '${INSTANCE}' already exists in ${ZONE}, skipping create."
else
  echo "==> Creating VM '${INSTANCE}'…"
  "${GCLOUD[@]}" compute instances create "${INSTANCE}" \
    --zone="${ZONE}" \
    --machine-type="${MACHINE_TYPE}" \
    --image-family="${IMAGE_FAMILY}" \
    --image-project="${IMAGE_PROJECT}" \
    --boot-disk-size="${DISK_SIZE_GB}GB" \
    --boot-disk-type=pd-balanced \
    --address="${EXTERNAL_IP}" \
    --tags="${NETWORK_TAG}" \
    --metadata-from-file=startup-script=<(printf '%s' "${STARTUP_SCRIPT}") \
    --shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring
fi

cat <<DONE

✓ VM ready.

  External IP : ${EXTERNAL_IP}
  SSH         : gcloud --project ${PROJECT_ID} compute ssh ${INSTANCE} --zone ${ZONE}
  API URL     : http://${EXTERNAL_IP}:${API_PORT}/api/v1/healthz

The startup script installs Docker + Compose plugin on first boot. It can take
1–2 minutes after 'create' completes for Docker to be ready. Verify with:

  gcloud --project ${PROJECT_ID} compute ssh ${INSTANCE} --zone ${ZONE} \\
    --command 'docker --version && docker compose version'

Next: deploy the code with

  PROJECT_ID=${PROJECT_ID} ZONE=${ZONE} INSTANCE=${INSTANCE} \\
    bash deploy/gcp/deploy.sh
DONE
