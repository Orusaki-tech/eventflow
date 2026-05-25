#!/usr/bin/env bash
# scripts/secrets.sh — manage EventFlow secrets in Google Secret Manager.
#
# Usage:
#   bash scripts/secrets.sh create   # create/update all secrets from .env.production
#   bash scripts/secrets.sh delete   # remove all secrets (irreversible!)
#   bash scripts/secrets.sh list     # list all EventFlow secrets and versions
#   bash scripts/secrets.sh fetch    # fetch all secrets and print as .env format
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
ENV_FILE="${ENV_FILE:-deploy/gcp/.env.production}"
PREFIX="eventflow"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: set PROJECT_ID or configure gcloud default project." >&2
  exit 1
fi

cmd="${1:-help}"

create() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: env file '${ENV_FILE}' not found. Set ENV_FILE or create deploy/gcp/.env.production" >&2
    exit 1
  fi

  echo "==> Reading secrets from ${ENV_FILE}"
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    secret_name="${PREFIX}-$(echo "${key}" | tr '[:upper:]' '[:lower:]')"

    # Read the full value: env files may have multi-line values (JSON creds).
    # Restore the rest of the line, then keep reading while lines end with '\'
    # (line continuation) or until the next KEY= pattern.
    full_value="${value}"
    while true; do
      IFS='' read -r next_line || break
      # If next line looks like a new KEY=, stop and push it back.
      if [[ "${next_line}" =~ ^[A-Z_][A-Z0-9_]*= ]]; then
        # Can't push back in pure bash; we accumulate it. This means the
        # secret up to the blank line will not include this next key.
        # Realistically, .env.production has one KEY= per secret with no
        # embedded newlines that look like KEY= — and multi-line values
        # are terminated by blank lines or the next KEY=.
        break
      fi
      full_value="${full_value}"$'\n'"${next_line}"
    done

    echo "  ${secret_name}..."
    # Use a temp file to avoid echo truncating or mangling binary/newline data.
    tmpfile=$(mktemp)
    printf '%s' "${full_value}" > "${tmpfile}"
    gcloud --project "${PROJECT_ID}" secrets versions add "${secret_name}" --data-file="${tmpfile}" 2>/dev/null \
      || gcloud --project "${PROJECT_ID}" secrets create "${secret_name}" \
        --labels="service=eventflow,managed=terraform" \
        --replication-policy="automatic" \
        --data-file="${tmpfile}"
    rm -f "${tmpfile}"
  done < <(grep -v '^$' "${ENV_FILE}")
  echo "✓ Done"
}

delete() {
  echo "==> Listing all secrets with prefix '${PREFIX}-'..."
  gcloud --project "${PROJECT_ID}" secrets list --filter="name:${PREFIX}-" --format="value(name)" | while read -r name; do
    echo "  Deleting ${name}..."
    gcloud --project "${PROJECT_ID}" secrets delete "${name}" --quiet
  done
  echo "✓ Done"
}

list() {
  gcloud --project "${PROJECT_ID}" secrets list --filter="labels.service=eventflow" \
    --format="table(name, replication, createTime)"
}

fetch() {
  gcloud --project "${PROJECT_ID}" secrets list --filter="labels.service=eventflow" --format="value(name)" | while read -r name; do
    key=$(echo "${name#"${PREFIX}-"}" | tr '[:lower:]' '[:upper:]')
    val=$(gcloud --project "${PROJECT_ID}" secrets versions access latest --secret="${name}" 2>/dev/null || true)
    if [[ -n "${val}" ]]; then
      echo "${key}=${val}"
    fi
  done
}

validate() {
  TEMPLATE=".env.example"
  if [[ ! -f "${TEMPLATE}" ]]; then
    echo "FATAL: Missing template file ${TEMPLATE} (should be checked in)." >&2
    exit 7
  fi
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing ENV_FILE ${ENV_FILE}">&2
    exit 2
  fi
  MISSING=0
  KEYS=$(grep -E '^[A-Z_][A-Z0-9_]*=' "${TEMPLATE}" | sed 's/=.*//')
  for key in $KEYS; do
    if ! grep -qE "^$key=" "${ENV_FILE}"; then
      echo "[MISSING] $key"
      MISSING=1
    fi
  done
  if [[ "$MISSING" == "1" ]]; then
    echo "ERROR: One or more required variables are missing from ${ENV_FILE}."
    exit 4
  else
    echo "All required environment variables are present in ${ENV_FILE}."
  fi
}

case "${cmd}" in
  create) create ;;
  delete) delete ;;
  list)   list ;;
  fetch)  fetch ;;
  validate) validate ;;
  *)
    echo "Usage: $0 {create|delete|list|fetch|validate}"
    echo ""
    echo "  create   - create/update all secrets from ENV_FILE (default: deploy/gcp/.env.production)"
    echo "  delete   - delete all EventFlow secrets"
    echo "  list     - list all EventFlow secrets"
    echo "  fetch    - print all secrets as KEY=VALUE format"
    echo "  validate - check that all required keys (from .env.example) are set in ENV_FILE"
    exit 1
    ;;
esac
