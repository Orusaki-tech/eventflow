# EventFlow (backend scaffold)

FastAPI backend scaffold following *Architecture Patterns with Python* patterns:
domain model + service layer + repository + unit of work + message bus + CQRS read models.

## Quickstart

Create a virtualenv and install deps:

```bash
python3 -m pip install -r requirements.txt
```

Copy environment template:

```bash
cp .env.example .env
```

### Instagram reliability (yt-dlp cookies)

Instagram frequently requires login and/or rate-limits unauthenticated scraping. To make link metadata + preview extraction more reliable, provide a cookies file for `yt-dlp`:

- Set `YTDLP_COOKIE_FILE` to the path of a Netscape `cookies.txt` file.
- In Docker, mount that file into the `api` container and set `YTDLP_COOKIE_FILE` to the in-container path.

### Run everything with Docker Compose (fastest)

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

For **Discover / carousel** smoke tests against Postgres, optionally insert demo `community_events`:

```bash
python3 scripts/seed_discovery_demo.py --dry-run   # verify DB + table
python3 scripts/seed_discovery_demo.py              # optional demo rows
```

Use `--organizer-user-id <Supabase-user-uuid>` so the mobile “Follow organizer” flow matches a real account.

API is at `http://localhost:8000`.

```bash
curl http://localhost:8000/api/v1/alerts/health
```

### Health

- `GET /api/v1/healthz`

### Local run (without Docker)

Set env vars (or `.env`) including `DB_URL` and `REDIS_URL`, then:

```bash
uvicorn eventflow.entrypoints.fastapi_app:app --reload
```

## Auth (Supabase)

Set:

- `SUPABASE_JWKS_URL`
- `SUPABASE_JWT_ISSUER`
- `SUPABASE_JWT_AUDIENCE` (usually `authenticated`)

When these are set, requests must include `Authorization: Bearer <supabase_jwt>`.
If `SUPABASE_JWKS_URL` is unset, the API **only** falls back to a random user id in `env=local/test` (or when `ALLOW_UNAUTHENTICATED_LOCAL=true`).

## Migrations

```bash
alembic upgrade head
```

## Workers (Docker Compose)

Keep **Redis** and these services up for background behavior (same stack as `docker compose up`):

| Service | Role |
| --- | --- |
| `scheduler` | Runs APScheduler jobs persisted in Postgres (traffic checks, **snooze / delayed push** jobs, etc.). |
| `traffic_worker` | Consumes `event.due_for_traffic_check`, calls Maps, schedules traffic alerts. |
| `outbox_publisher` | Publishes outbox rows to Redis (`event.confirmed`, `event.cancelled`, `alert.scheduled`). |
| `scheduler_sideeffects` | Subscribes to confirm/cancel events and schedules or cancels scheduler jobs. |
| `push_sideeffects` | Subscribes to `alert.scheduled` and schedules one-shot Expo push jobs on the scheduler. |
| `push_sender` | Sends notifications via **Expo Push API** — set **`EXPO_ACCESS_TOKEN`** or pushes never leave the worker. |
| `calendar_sideeffects` | Optional Google Calendar sync side effects — set **`GOOGLE_CALENDAR_CREDENTIALS_JSON`** if used. |
| `community_embeddings_worker` | Maintains community listing embeddings when pgvector + pipeline are enabled. |

**Mobile snooze reminders** depend on: API → scheduler job → `push_sideeffects` → `push_sender` (with `EXPO_ACCESS_TOKEN`). If only `api` is running, snooze HTTP succeeds but no notification is delivered.

**Discover / feed / carousel** depend on: Postgres schema from **`alembic upgrade head`** (including `community_events` when migrations apply), plus rows in `community_events` (your data or `scripts/seed_discovery_demo.py`).

### Outbox retention

For long-running prod deployments, periodically prune published outbox rows:

```bash
python3 -m eventflow.workers.outbox_cleanup
```

### User locations (home/work)

Set a user's location via:

- `PUT /api/v1/users/me/locations/{label}` where `{label}` is `home` or `work`
- `GET /api/v1/users/me/locations/{label}`

### Calendar (.ics + Google OAuth)

- **.ics fallback**: `GET /api/v1/events/{event_id}/ics` returns `text/calendar` for a user-owned event.
- **Google OAuth**:
  - `GET /api/v1/auth/google/calendar/start` redirects to Google consent.
  - `GET /api/v1/auth/google/calendar/callback` persists an encrypted token row in `user_calendar_tokens`.

Env vars:

- `GOOGLE_CALENDAR_CREDENTIALS_JSON`: OAuth client JSON from Google Cloud Console.
- `GOOGLE_OAUTH_REDIRECT_URI`: e.g. `http://localhost:8000/api/v1/auth/google/calendar/callback`
- `CALENDAR_TOKEN_KEY`: Fernet key used to encrypt tokens at rest. Generate one with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Tests

```bash
python3 -m pytest -q
```

## GCP VM deployment (Docker Compose + systemd)

Long-term stable setup is a single GCE VM running Docker + Compose, with:

- Containers set to `restart: unless-stopped` in `docker-compose.yml`
- A `systemd` unit (`deploy/systemd/eventflow.service`) to bring the stack up on boot
- A reserved static external IP so the VM keeps the same address

Two scripts handle this end to end:

| Script | When to run | What it does |
|---|---|---|
| `deploy/gcp/provision-vm.sh` | once per VM | reserves a static IP, creates the VM, installs Docker via startup script, opens TCP `:8000` |
| `deploy/gcp/deploy.sh` | every deploy | tar-streams source to `/opt/eventflow`, copies env file, runs `docker compose up --build`, applies migrations, installs systemd unit, health-checks; writes **`apps/mobile/.env.deployment`** with `EXPO_PUBLIC_EVENTFLOW_API_URL` from the VM’s current public IP (restart Expo to pick it up; `.env.local` overrides if set) |

### One-time setup

```bash
gcloud auth login
gcloud config set project <PROJECT_ID>

# 1. Fill in production secrets (NOT committed to git).
cp deploy/gcp/.env.production.example deploy/gcp/.env.production
$EDITOR deploy/gcp/.env.production

# 2. Create the VM (defaults: us-central1-a, e2-small, debian-12).
bash deploy/gcp/provision-vm.sh
```

Override defaults with env vars, e.g. `ZONE=europe-west1-b MACHINE_TYPE=e2-medium bash deploy/gcp/provision-vm.sh`. The script prints the external IP when done; the API will be reachable at `http://<IP>:8000` after the first deploy.

### Deploy / redeploy

```bash
bash deploy/gcp/deploy.sh
```

Re-run any time after a code change. It is idempotent.

On success, the script regenerates **`apps/mobile/.env.deployment`** (gitignored) so the Expo app’s default API base URL tracks the VM address without hand-editing. Keep **`EXPO_PUBLIC_EVENTFLOW_API_URL`** unset in **`.env.local`** if you want that file to apply; set it there only when you need to override (e.g. local backend).

Common flags:

```bash
SKIP_BUILD=1 bash deploy/gcp/deploy.sh                      # restart only, no rebuild
INSTALL_SYSTEMD=0 bash deploy/gcp/deploy.sh                 # skip systemd refresh
ENV_FILE=deploy/gcp/.env.staging bash deploy/gcp/deploy.sh  # different env file
```

### Operating the VM

```bash
# SSH in
gcloud compute ssh eventflow-api --zone us-central1-a

# Tail logs
gcloud compute ssh eventflow-api --zone us-central1-a \
  --command 'cd /opt/eventflow && sudo docker compose logs -f --tail=200 api'

# Restart everything (will also happen on reboot via systemd)
gcloud compute ssh eventflow-api --zone us-central1-a \
  --command 'sudo systemctl restart eventflow.service'
```

### Production hardening (recommended before going live)

The defaults are fine for staging but you'll want to tighten these for prod:

- **Don't expose Postgres/Redis publicly.** Remove `ports:` for `postgres` and `redis` in `docker-compose.yml` (compose's internal network is enough — only `api` needs them). The provisioning firewall only opens `:8000`, but compose host bindings on `0.0.0.0` would still expose them via the VM's external IP if those ports were open.
- **Change the Postgres password.** It's hardcoded as `secret` in `docker-compose.yml`. Either parametrize via the env file or move the DB to Cloud SQL / Supabase and unset the local `postgres` service.
- **Put a TLS terminator in front.** Either run Caddy/Traefik on the VM as a reverse proxy with a Let's Encrypt cert, or front the VM with a GCP HTTPS load balancer.
- **Back up Postgres.** `postgres-data` is a docker volume on the boot disk. Either snapshot the disk on a schedule or move to Cloud SQL.

