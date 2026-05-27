import re

with open('.github/workflows/deploy.yml', 'r') as f:
    content = f.read()

old_script = """              # Pull secrets from Secret Manager into .env
              sudo bash -c '
                : > /opt/eventflow/.env
                chmod 600 /opt/eventflow/.env
                for secret in \\$(gcloud secrets list --filter=\\"labels.service=eventflow\\" --format=\\"value(name)\\" 2>/dev/null); do
                  key=\\$(echo \\"\\$secret\\" | sed \\"s/^eventflow-//\\" | tr '[:lower:]' '[:upper:]')
                  val=\\$(gcloud secrets versions access latest --secret=\\"\\$secret\\" 2>/dev/null || true)
                  if [ -n \\"\\$val\\" ]; then
                    echo \\"\\$key=\\$val\\" >> /opt/eventflow/.env
                  fi
                done
              '

              # Authenticate Docker to Artifact Registry
              sudo gcloud auth configure-docker --quiet ${REGION}-docker.pkg.dev 2>/dev/null || true

              # Pull only the API image (other images are cached)
              sudo docker pull ${{ env.IMAGE_TAG }}

              # Start only essential services (e2-small can't run all workers)
              sudo IMAGE_TAG=${{ env.IMAGE_TAG }} docker compose up -d --remove-orphans api caddy redis

              # Run migrations (with timeout to avoid hanging on DB issues)
              sleep 10
              for i in \\$(seq 1 5); do
                timeout 30 sudo docker compose exec -T api alembic upgrade heads && break
                echo 'alembic attempt '\\$i' failed, retrying…'
                sleep 5
              done
              # All attempts exhausted
              if [ "\\$i" -eq 5 ] && ! timeout 10 sudo docker compose exec -T api alembic current 2>/dev/null | grep -qE '^[0-9a-f]{12}'; then
                echo 'FATAL: alembic migration failed after 5 attempts' >&2
                exit 1
              fi"""

new_script = """              # Pull secrets from Secret Manager securely
              cat << 'INNEREOF' > /tmp/pull_secrets.sh
#!/bin/bash
: > /opt/eventflow/.env
chmod 600 /opt/eventflow/.env
for secret in \\$(gcloud secrets list --filter="labels.service=eventflow" --format="value(name)" 2>/dev/null); do
  key=\\$(echo "\\$secret" | sed 's/^eventflow-//' | tr '[:lower:]' '[:upper:]')
  val=\\$(gcloud secrets versions access latest --secret="\\$secret" 2>/dev/null || true)
  if [ -n "\\$val" ]; then
    val_escaped=\\$(echo "\\$val" | sed "s/'/'\\\\\\\\''/g")
    echo "\\$key='\\$val_escaped'" >> /opt/eventflow/.env
  fi
done
INNEREOF
              sudo bash /tmp/pull_secrets.sh
              rm -f /tmp/pull_secrets.sh

              # Authenticate Docker to Artifact Registry
              sudo gcloud auth configure-docker --quiet ${REGION}-docker.pkg.dev 2>/dev/null || true

              # Pull only the API image (other images are cached)
              sudo docker pull ${{ env.IMAGE_TAG }}

              # Start only essential services (e2-small can't run all workers)
              # Inject DOMAIN so Caddy can automatically provision HTTPS if set
              sudo IMAGE_TAG=${{ env.IMAGE_TAG }} DOMAIN=${{ vars.DOMAIN }} docker compose up -d --remove-orphans api caddy redis

              # Run migrations (with timeout to avoid hanging on DB issues)
              sleep 10
              success=false
              for i in \\$(seq 1 5); do
                if timeout 30 sudo docker compose exec -T api alembic upgrade heads; then
                  success=true
                  break
                fi
                echo "alembic attempt \\$i failed, retrying…"
                sleep 5
              done

              if [ "\\$success" = "false" ]; then
                echo "FATAL: alembic migration failed after 5 attempts" >&2
                exit 1
              fi"""

content = content.replace(old_script, new_script)

with open('.github/workflows/deploy.yml', 'w') as f:
    f.write(content)
