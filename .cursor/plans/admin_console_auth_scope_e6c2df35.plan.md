---
name: Admin console auth scope
overview: Introduce a centralized admin-user guard tied to **ADMIN_USER_IDS** + Supabase JWT for the browser admin UI; retain **ADMIN_API_TOKEN** for scripts only. Ship Phase 1 read-only API routes and a minimal **apps/web-admin** Next.js shell with the same Supabase + API-proxy pattern as web-business. Defer ticketing and rich moderation workflows to later phases.
todos:
  - id: deps-require-admin-user
    content: Add shared require_admin_user (ADMIN_USER_IDS + JWT); refactor venues _is_admin to use it
    status: in_progress
  - id: api-admin-console-readonly
    content: "New admin_console router: /me, /summary, paginated businesses, community-events, poster-assets + schemas"
    status: pending
  - id: app-web-admin-scaffold
    content: Create apps/web-admin (Supabase login, API proxy client, layout gate, summary + 3 tables MVP)
    status: pending
  - id: docs-env-deploy
    content: Document ADMIN_USER_IDS + separate Vercel project vars for web-admin in deploy/example docs
    status: pending
isProject: false
---

# Admin console: auth recommendation and implementation plan

## Auth recommendation (senior default)

| Actor | Mechanism | Why |
|------|-----------|-----|
| **Humans (browser admin UI)** | **`ADMIN_USER_IDS`** + **`Authorization: Bearer`** (Supabase JWT) | Matches existing [`_is_admin`](eventflow/entrypoints/api/routes/venues.py) / venue PATCH pattern; supports Supabase MFA/session UX; **no long-lived secret in client JS**. |
| **Automation (scripts, cron, internal)** | **`X-Admin-Token`** + **`ADMIN_API_TOKEN`** | Already implemented [`require_admin_api_token`](eventflow/entrypoints/dependencies.py); keep for tooling — **never** expose as `NEXT_PUBLIC_*`. |

**Not chosen for MVP:** Supabase custom JWT claims / roles — better long-term RBAC, but adds Auth Hook / claim plumbing and migration work; revisit after the console proves value.

**Implementation detail:** Add a single FastAPI dependency **`require_admin_user`** (raises 403) that parses **`ADMIN_USER_IDS`** the same way as `_is_admin` today, and **optionally** refactor [`venues.py`](eventflow/entrypoints/api/routes/venues.py) to call that helper to avoid drift.

```mermaid
flowchart LR
  subgraph browser [Admin browser]
    NextAdmin[web-admin Next.js]
  end
  subgraph api [FastAPI]
    JwtDeps[get_current_user_id]
    AdminCheck[require_admin_user]
    Routes[/admin/console routes]
  end
  NextAdmin -->|"Bearer Supabase JWT"| JwtDeps
  JwtDeps --> AdminCheck
  AdminCheck --> Routes
```

---

## Backend — Phase 1 (read-only directory)

**New router** e.g. [`eventflow/entrypoints/api/routes/admin_console.py`](eventflow/entrypoints/api/routes/admin_console.py) (name can be `admin_console` tag), mounted under **`/api/v1`** in [`fastapi_app.py`](eventflow/entrypoints/fastapi_app.py).

All routes: **`Depends(require_admin_user)`** (JWT admin only for these).

Suggested endpoints (minimal, paginated, cursor or offset/limit):

1. **`GET /admin/console/me`** — `{ ok: true, user_id }` — cheap gate for the Next layout (403 if not admin).
2. **`GET /admin/console/summary`** — coarse counts: businesses, community_events, poster_assets, event_drafts (optional), users-derived metric (see below).
3. **`GET /admin/console/businesses`** — reuse / mirror fields from existing business listing patterns ([`product_gap.py`](eventflow/entrypoints/api/routes/product_gap.py)); pagination + optional search.
4. **`GET /admin/console/community-events`** — paginated listing from `community_events` (id, user_id, title, start_time, venue, source, poster_image_uri, attached business if joined).
5. **`GET /admin/console/poster-assets`** — paginated rows from [`poster_assets`](eventflow/adapters/orm.py) (`id`, `content_sha256`, `dhash64`, `created_at`, `content_type`) plus **aggregate link counts** via subqueries on `event_sources.poster_asset_id` (and optionally draft/event linkage counts).

**“Users on platform” MVP:** There is no dedicated `users` table in the snippets reviewed; Phase 1 should expose **distinct `user_id` rollups** from `community_events`, `event_drafts`, `businesses` (owners), or similar SQL views — not a full CRM profile. Label the UI honestly as **“active user ids (derived)”** until you add a proper user dimension table or sync from Supabase Auth.

**Schemas:** Add compact Pydantic response models in [`schemas.py`](eventflow/entrypoints/api/schemas.py).

**Poster thumbnails (defer or Phase 1b):** Listing rows without bytes is enough for MVP tables. Serving images requires an **admin-only** stream endpoint from [`PosterStore`](eventflow/adapters/poster_store.py) by `poster_id` — plan as **Phase 1b** after read-only list works.

**Existing token-admin routes:** Leave [`require_admin_api_token`](eventflow/entrypoints/dependencies.py) routes as-is (verified flag, video moderation). Optionally document that **operators** should use the console (JWT) while **automation** keeps `X-Admin-Token`.

---

## Frontend — Phase 1 (`apps/web-admin`)

**New Next.js app** [`apps/web-admin`](apps/web-admin) (parallel to [`apps/web-business`](apps/web-business)):

- Same patterns: Supabase browser client (singleton), **`NEXT_PUBLIC_EVENTFLOW_API_PROXY`** + **`EVENTFLOW_UPSTREAM_URL`** on Vercel, [`efFetch`-style](apps/web-business/src/lib/eventflow-api.ts) client calling **`/api/v1/admin/console/...`** (through proxy).
- **Routes:** `/login`, `/` dashboard (summary cards), `/businesses`, `/listings`, `/posters` — tables with pagination state in URL search params where practical.
- **Gate:** After session exists, call **`GET /admin/console/me`**; on 403 show **“Not an admin”** and sign-out link (avoid silent failures).

**Why a separate app:** Blast radius, separate Vercel project/env, and clearer security posture than mixing organizer portal with global admin in one deployment.

**Operational:** Document **`ADMIN_USER_IDS`** in [`deploy/gcp/.env.production.example`](deploy/gcp/.env.production.example) (comma-separated Supabase **auth user UUIDs**).

---

## Deferred (explicitly out of Phase 1)

- **Ticketing / free RSVPs:** New bounded context (inventory, registration, check-in, fraud limits). Needs schema + product design — **Phase 3+**.
- **Venue enrichment workflows:** Building on [`venues`](eventflow/entrypoints/api/routes/venues.py) — admin UI to attach canonical venue to listings — **Phase 2**.
- **Full moderation queues** (shared_link rejections, merge duplicates beyond counts): **Phase 2** once directory stabilizes.
- **Audit log table:** **Phase 2** recommended before any destructive/write admin actions.

---

## Verification

- Local: set **`ADMIN_USER_IDS`** to your Supabase user id; hit new endpoints with Bearer token — expect 200 vs 403 for non-admin.
- **`ADMIN_API_TOKEN`** unchanged — curl `X-Admin-Token` paths still work.
- Next: `npm run build` for `web-admin`; smoke login + summary page against staging API.
