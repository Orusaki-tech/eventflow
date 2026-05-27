# EventFlow — Complete User & Business Journey Map

> **Executive Overview** — EventFlow is a social event discovery platform connecting **attendees** (mobile users) with **organisers** (businesses) through an AI-powered, TikTok-style discovery feed. Users import events from any URL, discover personalised content, buy tickets, and share plans with friends. Businesses create listings, sell tickets, run promotions, and get paid — all within one platform.

---

## Platform Architecture

```
┌─ Mobile App (React Native) ─┐  ┌─ Business Portal (Next.js) ─┐  ┌─ Admin Console (Next.js) ─┐
│  Inbox │ Calendar │ Capture  │  │  Dashboard │ Listings         │  │  Summary │ Moderation     │
│  Discover │ Profile          │  │  Products │ Payouts │ Taps    │  │  Claims │ Payouts │Users  │
└──────────────────────────────┘  └──────────────────────────────┘  └────────────────────────────┘
         │                               │                                  │
         └───────────────────────────────┼──────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │        EventFlow API (FastAPI)           │
                    │  ~80 endpoints · Hexagonal Architecture  │
                    └────────────────────┬────────────────────┘
                                         │
      ┌──────────┬───────────┬───────────┼───────────┬───────────┬──────────┐
      │          │           │           │           │           │          │
  [Supabase] [PostgreSQL]  [Redis]   [Cloud SQL]  [Redis]    [Stripe]   [Expo]
  (Auth/JWT)  (Core DB)  (Cache)    (Postgres)  (Pub/Sub)  (Payments) (Push)
      │          │           │           │           │           │          │
      └──────────┴───────────┴───────────┴───────────┴───────────┴──────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                         [Gemini AI]        [Google Maps]        [yt-dlp]
                        (Poster OCR)       (Travel ETA)      (URL Parsing)

  Background Workers (10):
  Scheduler → Push Sender → Traffic Monitor → Calendar Sync → Outbox Publisher
  → Community Embeddings → Push Sideeffects → Calendar Sideeffects → Outbox Cleanup
```

---

## Part 1: End User Journeys

### Journey 1 — Event Discovery

*From opening the app to finding something to do.*

1. Open **Discover** tab → loads the **unified feed** (TikTok-style vertical pager)
2. Feed blends **three content types** in a fixed 66/16/16 pattern:
   - **Feed Videos** (66%) — business promotional clips, auto-play with mute toggle, business logo overlay, WhatsApp CTA
   - **Community Events** (16%) — poster image with date/venue badge, "X friends going" social proof
   - **Affiliate Products** (16%) — product image with price, seller name, "Inquire on WhatsApp" button
3. Feed is **personalised**: followed users' and businesses' content appears first (V2 Feed Home), then trending/sponsored
4. **Semantic search** via pgvector — type a query, get ranked event results
5. **Business profiles** — tap business name → see all listings, follower count, logo, verified badge, contact info
6. **Follow businesses** → their events appear in your home feed

**Key screens:** `DiscoverHomeScreen`, `CommunityListingDetail`, `BusinessProfileView`

### Journey 2 — Event Import & Sharing

*From any external link to a confirmed event in under 10 seconds.*

1. Tap **Capture** (camera icon) or share button → choose method:
2. **Paste any URL** (Instagram, TikTok, YouTube, Facebook, event page, etc.)
3. System extracts event info via **yt-dlp + Gemini AI** — handles 30+ platforms
4. AI extracts: `title`, `start_time`, `venue`, `price`, `confidence_score`
5. **Poster upload** — snap a photo of a flyer → AI reads text from image
6. **Image upload** — any event poster image
7. **Text paste** — copy/paste event description from any source
8. **ICS import** — upload calendar file (`.ics`)
9. A draft is created with the extracted data
10. **Admin shortcuts**: if URL was pre-approved by admin or registered as a listing alias (business), the AI step is bypassed entirely

**Key screens:** `CaptureScreen`, `ImportLink`, `PosterImport`, `Processing`, `DraftDetail`

### Journey 3 — Event Management

*After importing: edit, confirm, and manage your event.*

1. **Edit draft** — correct AI's extraction: title, date/time, venue (Google Places autocomplete), price, description, confidence score
2. **Confirm draft** → becomes a **Scheduled Event**
3. **Set visibility** — `public` (discoverable) or `private` (invite-only)
4. **Resolve venue** — Google Places autocomplete or manual lat/lng coordinates
5. **Write descriptions** — public-facing or close-friends-only
6. **Get travel ETA** — Google Maps travel time from any origin to venue
7. **Set alerts** — reminder before event starts, leave-now traffic alert
8. **Download .ics** — add to Apple/Google calendar
9. **Link to device calendar** — two-way sync with phone calendar
10. **Cancel event** — notifies attendees, cancels alerts

**Key screens:** `DraftEdit`, `EventDetail`, `ManualVenue`

### Journey 4 — Social Groups

*Plan events with friends.*

1. **Create group** → "Weekend Crew" → gets unique `invite_token`
2. **Share invite link** — anyone with the token joins via `POST /groups/join-by-token`
3. **Share an event to the group** → all members see it in their group feed
4. **RSVP** — `going`, `maybe`, or `declined`
5. **Attending friends count** — feed shows how many friends are attending each event (joined from `group_rsvps`)
6. **Pin an event** to highlight it in the group
7. **Group event feed** — all events shared to the group, sorted by date

**Key screens:** `Inbox` (group events), `EventDetail` (RSVP)

### Journey 5 — Follow System

*Stay connected with people and businesses.*

1. **Follow users** → their public events appear in your personalised feed
2. **Follow businesses** → their listings appear in your feed
3. Feed priority: followed users' events → followed businesses' events → trending/sponsored
4. **Business follower count** shown on business profile (social proof)

**Data model:** `follows` (user→user), `business_follows` (user→business)

### Journey 6 — Buying Tickets

*From discovery to the door.*

1. Browse event listing → tap to see **ticket types**:
   - **Free** (GA, $0)
   - **Paid** (VIP, Early Bird, Regular — any price in KES)
2. Select quantity → review total
3. **Purchase** via Stripe (card) or MPESA (mobile money — East Africa)
4. Order confirmed immediately with receipt: `EVT-YYMM-######`
5. Each ticket gets a scannable short code: `EVT-A3X9`
6. **Order history** — view all past purchases with ticket codes
7. **Resend tickets** — re-fetch codes anytime
8. **At the venue** — event organiser scans the short code → ticket marked `used`
9. Check-in updates: `checked_in_at`, `checked_in_by` (organiser)
10. **Unauthorised scanning blocked** — only the listing owner can check in

**Points earned:** 1 point per KES 100 spent (loyalty currency)

### Journey 7 — Claims & Support

*When something goes wrong.*

1. File a claim on any order — types: `ticket_not_received`, `event_cancelled`, `refund`, `other`
2. Claim enters "open" status → visible to admin console
3. **Admin reviews** → approves or denies
4. If approved → order refunded, all tickets voided (`status = refunded`)
5. If denied → order and tickets remain active

### Journey 8 — Points & Premium

*Loyalty rewards and subscription monetisation.*

| Feature | Free Tier | Premium (KES 300/mo) |
|---|---|---|
| Daily video watches | 10/day | Unlimited |
| Points earned on tickets | 1 pt / KES 100 | 1 pt / KES 100 |
| Points earned on video watches | 1 pt / completed | 1 pt / completed |
| Points redemption | 10 pts min = KES 50 discount | Same |

1. **Earn points**: buy tickets, watch videos
2. **Redeem**: 10+ points → discount code `PTS-XXXX`, 1 pt = KES 5
3. **Subscribe to Premium** via Stripe Checkout (card) or direct activation
4. Stripe webhook handles: subscription created, updated, cancelled
5. **Subscription status** — `GET /subscriptions` returns active period
6. **Cancel anytime** — `DELETE /subscriptions/cancel`

### Journey 9 — Calendar & Notifications

*Never miss an event.*

1. **Google Calendar OAuth** — link account, confirmed events sync automatically
2. **Push notifications** via Expo Push API:
   - **Reminder** — before event starts (user-configurable)
   - **Traffic alert** — Google Maps travel time suggests leaving early
   - **Snooze** — postpone the leave-now alert
3. **Device calendar link** — maps events to iPhone/Android calendar
4. **Calendar screen** — "Today" and "Upcoming" segments for all your events

### Journey 10 — Places & Venues

*Know exactly where you're going.*

1. **Google Places autocomplete** — find venues while typing
2. **Venue search** — find existing venues by name
3. **Manual venue creation** — add with name, address, lat/lng
4. **Travel ETA** — real-time driving time from any origin
5. **Saved locations** — save "Home" and "Work" addresses for one-tap ETA

---

## Part 2: Business Journeys

### Journey B1 — Business Onboarding

*Get set up on the platform in minutes.*

1. **Create business profile** — name, WhatsApp number (primary CTA), description, logo URL, website, contact email
2. **Ownership** — creator is set as `owner_user_id`
3. **Request verification** → admin toggles `verified = true` → verified badge on profile
4. **Web portal access** — `apps/web-business/` Next.js portal for all management
5. **Configure payouts** — MPESA Till/Paybill or Bank Transfer
6. **Choose tap pack** — advertising credits (starter/growth/pro/unlimited)

### Journey B2 — Creating & Managing Listings

*What businesses post.*

1. **Create community event** — title, start time, venue, description, poster image URL
2. **Attach business** to listing via `business_listing_attachments` (must own both)
3. **Upload event video** → admin moderation → appears as hero video on listing
4. **Register share alias** — URLs that auto-resolve to this listing when users share them
5. **Set sponsored rank** — higher value = premium placement in discovery feed
6. **Edit listing** anytime — title, time, venue, description, poster

### Journey B3 — Video Promotion

*Get seen in the discovery feed (66% of all slots).*

1. **Publish feed video** — title, video URI, thumbnail URI, type (`promo`/`countdown`/`highlights`)
2. Optionally link to a community event + business
3. Video enters **admin moderation**: `pending` → `approved` | `rejected`
4. Once approved → appears in **66% of unified feed slots**
5. **Performance metrics**: views count, completion rate, WhatsApp taps

### Journey B4 — Selling Tickets

*The core revenue stream.*

1. **Create ticket types** per listing — multiple tiers:
   - General Admission (free or paid)
   - VIP (higher price, limited quantity)
   - Early Bird (discounted, limited window)
2. Each type has: name, price, quantity, sale window, refund window
3. **Sales dashboard** per listing:
   - Tickets sold per type
   - Gross revenue / platform fees (8%) / net to business
   - Check-in count (QR-scanned attendees)
4. **Affiliate products** can be linked to any listing, visible only to ticket buyers

### Journey B5 — WhatsApp Taps & Tap Packs

*The primary conversion channel.*

1. Every listing shows a **WhatsApp button** (using business's WhatsApp number)
2. User taps → opens `wa.me/{number}` chat
3. Each tap counted as analytics event (`whatsapp_tap`)
4. Businesses buy **tap packs** (advertising credit):

| Plan | Taps | Price (KES) |
|---|---|---|
| Starter | 10 | 200 |
| Growth | 50 | 750 |
| Pro | 200 | 2,500 |
| Unlimited | Unlimited | 5,000/mo |

### Journey B6 — Affiliate Products

*Commerce between businesses.*

1. **Create product** — title, description, price, image URI
2. **Link to any event** — even events hosted by other businesses
3. If different businesses → event owner must **approve affiliate request**
4. **Commission split** (default: 80/10/10):
   - 80% — Product seller
   - 10% — Event owner (listing host)
   - 10% — Platform
5. Products visible **only to ticket buyers** of the linked event
6. Products appear in **16% of unified feed slots**
7. WhatsApp inquiry → goes directly to product seller

### Journey B7 — Getting Paid

*Money out.*

1. **Configure payout method** — MPESA Till, MPESA Paybill, or Bank Transfer
2. **Set frequency** — manual, weekly, or monthly
3. **Minimum payout** — KES 500
4. **Revenue dashboard** — total gross, platform fees, net available
5. **Request payout** → enters `pending` status
6. **Admin processes** → marks as `paid`, records payment reference
7. **History** — view all past payouts

### Journey B8 — Analytics

*Know what's working.*

1. **Dashboard**: total revenue, fees, net, tickets sold, check-in rate
2. **Per-listing analytics**:
   - `impression` — how many times it appeared in feeds
   - `save` — how many users saved it
   - `whatsapp_tap` — conversion via WhatsApp
3. **Video performance**: views, completion rate, taps
4. **Affiliate earnings**: commissions earned

---

## Part 3: User–Business Interaction Matrix

| User Action | Business Benefit |
|---|---|
| Views listing in feed | Impression tracked |
| Watches feed video | View count + completion rate |
| Taps WhatsApp button | Direct customer inquiry (analytics tracked) |
| Follows business | Follower count + appears in user's feed |
| RSVPs to event | Attendance signal (social proof for others) |
| Buys ticket | Revenue (minus 8% platform fee) |
| Checks in at venue | Verified attendance + proof of delivery |
| Views affiliate product | Potential commission pipeline |
| Inquires via WhatsApp | Direct customer contact |
| Files a claim | Resolution through admin |

| Business Action | User Experience |
|---|---|
| Creates listing | New event in discovery feed |
| Publishes video | New content (66% of feed) |
| Sets ticket types | Available for purchase |
| Gets verified | Trust signal (verified badge) |
| Approves affiliate product | Product visible (if ticket holder) |
| Registers share alias | Instant draft creation when sharing URL |

---

## Part 4: Money Flow

```
USER                          EVENTFLOW                       BUSINESS
 │                                │                                │
 │── Buys ticket (KES 500) ─────>│                                │
 │                                │                                │
 │  1 point earned                │                                │
 │   (KES 500 / 100)              │                                │
 │                                │                                │
 │                                │  Platform takes 8% fee         │
 │                                │  Fee = KES 40                  │
 │                                │                                │
 │                                │  Business net = KES 460        │
 │                                │                                │
 │                                │<── Requests payout ────────────│
 │                                │                                │
 │       Admin processes payout   │                                │
 │                                │── MPESA/Bank transfer ────────>│
 │                                │        KES 460                 │
 │                                │                                │
 ───────────────────────────────────────────────────────────────────

 === REVENUE STREAMS ===

 TICKET PLATFORM FEE:       8% of every ticket sale      → EventFlow
 TAP PACKS (ADVERTISING):   KES 200–5,000/month          → EventFlow
 PREMIUM SUBSCRIPTIONS:     KES 300/month (via Stripe)   → EventFlow
 AFFILIATE COMMISSIONS:     10% of each product sale     → EventFlow
```

| Stream | Rate | Payer | Collected Via |
|---|---|---|---|
| Ticket fee | 8% of price | Business | Held from payout |
| Tap packs | Flat fee | Business | Direct (stub) |
| Premium | KES 300/mo | User | Stripe |
| Affiliates | 10% per sale | Seller | Held from payout |

---

## Part 5: Database Model (Key Tables)

| Table | Rows Expected | Purpose |
|---|---|---|
| `businesses` | 2 | Business profiles |
| `community_events` | 5 | Event listings (owned by businesses) |
| `business_listing_attachments` | 5 | Links businesses → events |
| `event_videos` | 6 | Listing hero videos (1 pending) |
| `feed_videos` | 5 | Promotional videos (1 pending) |
| `ticket_types` | 11 | Pricing tiers across events |
| `orders` | 3 | Purchase transactions |
| `tickets` | 12 | Individual scannable tickets |
| `products` | 3 | Affiliate product listings |
| `product_event_links` | 3 | Products linked to events |
| `groups` | 1 | Friend group |
| `group_memberships` | 3 | Group members |
| `group_rsvps` | 3 | RSVPs to shared events |
| `follows` | 2 | User→user follows |
| `business_follows` | 4 | User→business follows |
| `shared_link_listings` | 2 | Pre-approved + rejected URLs |
| `poster_assets` | 3 | Poster image metadata |
| `poster_asset_parses` | 3 | AI parse results |
| `claims` | 1 | User claim for resolution |
| `user_subscriptions` | 1 | Alice's premium subscription |
| `feed_watch_log` | 4 | Video watch history |
| `listing_analytics_events` | 6 | Impression/save/tap events |
| `venues` | 3 | Venue directory |

---

## Part 6: Key Metrics & KPIs

| Area | Metric | How |
|---|---|---|
| **Acquisition** | Events imported via URL | AI parse success rate |
| **Engagement** | Feed views / video completions | Watch quota, completion rate |
| **Social** | Groups created / RSVPs / follows | Social graph density |
| **Conversion** | Tickets purchased / revenue | Orders, platform fees |
| **Business** | Listings created / videos published | Active businesses |
| **Monetisation** | Premium subs / tap packs sold | MRR |
| **Platform** | Total users, businesses, events | Admin dashboard |

---

## Part 7: Technical Differentiators

| Feature | What It Does |
|---|---|
| **AI Event Parsing** | Gemini extracts event details from poster images, URLs, and text — supports 30+ platforms via yt-dlp |
| **TikTok-style Feed** | Vertical pager blends videos, events, and affiliate products with social proof (attending friends) |
| **pgVector Search** | 64-dimensional semantic embeddings for natural-language event search |
| **Social Graph** | User-to-user follows, business follows, groups with RSVPs — personalised feed |
| **Multi-platform Sharing** | Share from Instagram, TikTok, YouTube, Facebook, event pages, or any URL |
| **Offline-First Posters** | SHA-256 content-addressable deduplication + Gemini parse caching |
| **Outbox Pattern** | Transactional event publishing (DB → Redis → workers) for reliability |
| **Modular Workers** | 10 background workers handle push, calendar, traffic, embeddings, payouts |
| **Stripe Integration** | Premium subscriptions with full webhook lifecycle management |
| **Tap Pack Advertising** | Prepaid WhatsApp inquiry credits — measurable ROI for businesses |
