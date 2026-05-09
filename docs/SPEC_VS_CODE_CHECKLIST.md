# EventFlow Product Spec v2.0 vs codebase

Living checklist. Update when features ship.

## Phase 1 — Personal planner / MVP

| Spec area | Status |
|-----------|--------|
| AI image ingestion (camera, gallery, share) | Done |
| URL / Instagram carousel ingestion (user-initiated) | Done |
| Draft review + explicit confirm | Done |
| In-app Today / Upcoming | Done |
| Leave Now pipeline (T−3h traffic job, alerts, push) | Done |
| Native device calendar (EventKit / Calendar Provider) | Done (`expo-calendar` + device IDs persisted via API) |
| Google Calendar OAuth sync | Done (worker `calendar_sideeffects` + API OAuth) |
| Cancel removes Google Calendar row | Done (`delete_event` + worker on `event.cancelled`) |
| Push: deep link data + Navigate / Snooze | Done (Expo `data` payload + `/events/snooze-alert`) |
| URL moderation `pending\|approved\|rejected` | Done (`shared_link_listings` + share handlers) |

## Phase 2 — Business listings

| Spec area | Status |
|-----------|--------|
| Public listings + claim OTP flow | Partial (`POST /api/v1/businesses`, attachments table ready; OTP/claim workflow not fully built) |
| WhatsApp CTA + tap analytics | Partial (`POST /api/v1/listing-analytics` with `whatsapp_tap`; mobile CTA surfaces optional) |
| Business portal (editor, analytics hooks) | Stub (`GET /portal` HTML + APIs above) |

## Phase 3 — Social

| Spec area | Status |
|-----------|--------|
| Follow / unfollow | Done (`POST/DELETE /api/v1/follows/{user}`) |
| Composite `/feed/home` | Done (`GET /api/v1/feed/home`) |
| Groups: types, invite token, RSVP, pin | Done (API: join-by-token, RSVP, pin; mobile UI minimal) |

## Phase 4 — Monetisation

| Spec area | Status |
|-----------|--------|
| Event videos + moderation states | Partial (`POST /api/v1/event-videos`, `event_videos` table; automated moderation pipeline stub) |
| Carousel invariant poster slide 1 | Done (`GET /api/v1/listings/{id}/carousel`) |
| Stripe / M-Pesa placeholders | Stub (`POST /api/v1/billing/checkout-session`) |
