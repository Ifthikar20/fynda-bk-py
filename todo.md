# Outfi - Project Status

---

## Completed — Security

### Authentication & Authorization
- [x] Custom UUID-based User model with email authentication
- [x] JWT auth via `simplejwt` — access (1hr dev / 30min prod), refresh (7d dev / 1d prod)
- [x] Token rotation + blacklist on refresh & logout
- [x] Google OAuth 2.0 + Apple Sign In
- [x] Password validation (similarity, min length, common password, numeric checks)

### Rate Limiting & Throttling
- [x] DRF throttles — anon/auth per environment
- [x] Image upload throttles — anon: 20/hr, auth: 60/hr, burst: 5/min
- [x] Premium-aware daily quotas — Free: 5/day, Premium: 50/day image searches
- [x] IP-based rate limit middleware per endpoint

### Input Validation & Sanitization
- [x] Content-Type, request size, path traversal, parameter validation, JSON depth limiter
- [x] SQL injection & XSS pattern detection

### File Upload Security
- [x] Magic bytes validation, decompression bomb protection, EXIF stripping
- [x] SHA-256 hash dedup, resize + JPEG conversion

### API Protection & Anti-Enumeration
- [x] Honeypot paths, scanner detection, sequential ID enumeration detection
- [x] HMAC request signing, replay attack prevention, bot detection
- [x] Mobile app bypass via `X-Outfi-Mobile-Key` header

### Security Headers, TLS, CORS, CSRF
- [x] CSP, X-Frame-Options, HSTS, SSL redirect (production)
- [x] Secure cookies (HttpOnly, SameSite=Lax, Secure)
- [x] CORS whitelist (production), CSRF trusted origins

### Response Security
- [x] Sensitive data masking, error normalization, identical 404 responses

### IDOR Fix
- [x] SharedStoryboard IDOR fixed — list/create require `IsAuthenticated`
- [x] Delete/update scoped to `user=request.user` via `_get_owner_board()`
- [x] Public GET by token still works for share links
- [x] Private boards (`is_public=False`) only visible to owner

### Stripe Webhook Security
- [x] Signature verification via `STRIPE_WEBHOOK_SECRET`
- [x] Payment intent validation before activating subscriptions

---

## Completed — Apple Pay / Stripe Payments

### Payment Infrastructure (`payments/` app)
- [x] `Subscription` model — plan (free/premium_monthly/premium_yearly), status, Stripe IDs, billing cycle
- [x] `Payment` model — individual payment records with Stripe payment intent tracking
- [x] `is_premium` property on Subscription — checks plan + status + period end
- [x] Admin panel for Subscription and Payment models

### Endpoints (`/api/v1/payments/`)
- [x] `GET /status/` — current subscription status + feature limits
- [x] `POST /subscribe/` — creates Stripe PaymentIntent + ephemeral key for Apple Pay sheet
- [x] `POST /cancel/` — cancel subscription at period end
- [x] `GET /history/` — payment history (succeeded payments)
- [x] `POST /restore/` — restore subscription on reinstall/device switch (checks Stripe customer)
- [x] `POST /webhook/` — Stripe webhook handler (payment succeeded/failed, subscription updated/deleted, invoice paid)

### Apple Pay Flow
- [x] Backend creates PaymentIntent with `payment_method_types: ["card"]` (Apple Pay uses card token)
- [x] Returns `client_secret` + `ephemeral_key` + `publishable_key` for mobile SDK
- [x] Supports Apple Pay (primary), Google Pay, and card as fallback — same backend flow
- [x] Webhook activates subscription on `payment_intent.succeeded`
- [x] Recurring billing handled via `invoice.paid` webhook

### Premium Tier Enforcement
- [x] `DailyImageQuotaThrottle` now checks subscription status
- [x] Free tier: 5 image searches/day, 10 price alerts, 50 saved deals, 5 storyboards
- [x] Premium tier: 50 image searches/day, 100 price alerts, 1000 saved deals, 50 storyboards, ad-free
- [x] Upgrade prompt in throttle error message for free users

### Pricing
- [x] Premium 2 Weeks: $4.99
- [x] Premium Monthly: $9.99

### Configuration
- [x] `stripe>=8.0` added to requirements.txt
- [x] Settings: `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` from env
- [x] `payments` app in `INSTALLED_APPS`
- [x] URL routes at `/api/v1/payments/`
- [x] Migration: `payments/migrations/0001_initial.py`

---

## Completed — User Preferences & Features

### Preferences (UserPreferences model)
- [x] Push notifications — master toggle, deals, price alerts, weekly digest
- [x] Display — theme, currency, language
- [x] Search — default sort, show sold items, preferred sources
- [x] Location — `default_latitude`, `default_longitude`, `default_location_name`, `max_distance_miles`
- [x] Style — `preferred_gender`, `preferred_sizes`, `preferred_styles`
- [x] Privacy — save search history toggle, anonymous analytics toggle

### Location & Distance Wiring
- [x] Search + image search use saved location as fallback
- [x] `max_distance_miles` passed to Facebook Marketplace vendor for filtering
- [x] `preferred_gender` used as default in search

### Facebook Marketplace Distance Filter
- [x] `_within_distance()` filters results beyond user's max distance
- [x] Orchestrator forwards `max_distance` to Facebook vendor

### Storyboard Sharing
- [x] Public GET by share token — anyone with URL can view
- [x] `is_public` toggle — owner can make boards private via PUT
- [x] `share_url` included in list, create, GET, and update responses
- [x] Private boards return 404 to non-owners

### Background Remover Fix
- [x] Small image upscaling — images below 64px are upscaled via LANCZOS before processing
- [x] Minimum dimension check — rejects images below 10px with clear error
- [x] `pil_img.load()` — catches truncated/corrupt images before processing
- [x] Better error message: "Try a larger or clearer image"

### Other Completed Features
- [x] Saved Deals / Favorites, Brand Preferences, Search History
- [x] Price Alerts (full CRUD), Device & Push Token Management
- [x] Feed / Social, Sync & Offline Support, Pinterest Integration
- [x] Email Subscriptions, API Usage Tracking, Mobile Sessions
- [x] Gemini Vision Image Search, Blog / SEO Pipeline

---

## In Progress (Uncommitted Changes)

### Performance Optimizations
- [x] Reduce image max dimension 800 → 600
- [x] Shorter Gemini prompt + lower temperature/max tokens
- [x] Reduce vendor timeouts (20s/15s → 10s/8s)
- [x] Reduce search queries from 3 → 2, skip CLIP for image search
- [x] Faster EXIF stripping + set-based dedup

---

## YOUR PART — Pending

### Migrations
- [x] `mobile/0003_add_location_style_preferences` — applied
- [x] `payments/0001_initial` — applied

### Stripe Setup
- [x] Stripe sandbox account created (acct_1TILuq3I87vPzCFd)
- [x] API keys added to `.env` (pk_test, sk_test, whsec)
- [x] Stripe CLI installed + webhook forwarding tested
- [ ] Set up production Stripe webhook → `https://outfi.ai/api/v1/payments/webhook/`
- [ ] Enable Apple Pay in Stripe Dashboard → Settings → Payment Methods
- [ ] Switch to live keys (`pk_live_...` / `sk_live_...`) when going to production

### Flutter / Mobile App
- [x] `flutter_stripe` package added
- [x] Stripe initialized in `main.dart`
- [x] Payment service + paywall screen + `/premium` route
- [x] "Outfi Premium" card + restore purchase in profile
- [x] **Preferences screen** (`/preferences`) — location detect, max distance slider, gender, sizes, styles
- [x] **Distance filter** in search results — chip row with 10/25/50/100 mi options
- [x] **Storyboard is_public toggle** in share screen — switch between public/private
- [x] **Storyboard model** updated with `isPublic`, `viewCount` fields
- [x] **StoryboardService.togglePublic()** method added
- [x] **Fashion Timeline screen** (`/timeline`) — weekly + monthly views
- [x] Timeline entry add (title + mood), delete, share as storyboard link
- [x] Profile screen updated: Fashion Timeline + Preferences rows added
- [x] Router: `/preferences`, `/timeline` routes added
- [x] DealsBloc + DealService accept `maxDistance` parameter
- [ ] **Design custom paywall UI** — waiting for design direction
- [ ] Flutter submodule update

### Fashion Timeline (just implemented)
**Backend:**
- [x] `FashionTimelineEntry` model — user, date, title, image_url, outfit_data, mood
- [x] `GET /api/v1/mobile/timeline/?month=2026-04` — list entries for month
- [x] `POST /api/v1/mobile/timeline/` — add/update day's outfit
- [x] `DELETE /api/v1/mobile/timeline/<date>/` — remove entry
- [x] `POST /api/v1/mobile/timeline/share/` — generate shareable storyboard from date range
- [x] Migration: `mobile/0004_add_fashion_timeline`
**Flutter:**
- [x] Week view — 7-day list with outfit thumbnails, mood tags, tap to add
- [x] Month view — calendar grid with outfit indicators
- [x] Share button — creates storyboard link for the week/month
- [x] Add outfit sheet — title input + mood picker (cozy/bold/minimal/casual/formal/sporty/vintage/street)

### Gemini API Quota System (just implemented)
- [x] Per-user daily + bi-weekly limits aligned with $4.99/2wk subscription
- [x] Free: 3/day, 20/bi-week | Premium: 25/day, 250/bi-week
- [x] Separate `gemini_vision` endpoint tracking (cost: ~$0.0025/call)
- [x] Usage logged AFTER image validation (no wasted quota on bad uploads)
- [x] `GET /api/v1/mobile/usage/` — returns remaining quota + cost stats
- [x] Proactive logging: `QUOTA LOW` at ≤2 daily or ≤10 bi-weekly remaining
- [x] `QUOTA BLOCK` logged with user email, counts, and cost on limit hit
- [x] `APIUsageLog.get_period_stats()` — bi-weekly cost/count aggregation
- [x] `APIUsageLog.get_user_summary()` — full per-user dashboard data
- [x] Premium margin: 87% ($4.99 revenue, max $0.62 Gemini cost per 2wk)

### Server Downsizing (just implemented)
- [x] Gunicorn workers configurable via `GUNICORN_WORKERS` env (default: 2, set 1 for micro)
- [x] Celery concurrency reduced: 2 → 1
- [x] Redis: maxmemory 128MB + LRU eviction, AOF disabled (faster, less disk)
- [x] Postgres tuned: shared_buffers=64MB, work_mem=4MB, max_connections=30
- [x] Nginx: 1 worker, 512 connections (was auto/1024)
- [x] All containers have memory limits:
  - API: 512MB | Celery: 384MB | ML: 512MB | Postgres: 256MB | Redis: 192MB
- [x] ML healthcheck interval increased to 60s (less overhead)

### Migrations to Run
- [x] `mobile/0004_add_fashion_timeline` — applied
- [ ] `deals/0006_add_snapshot_path` — run `python manage.py migrate`

### S3 Setup
- [ ] Add bucket policy for public reads on `storyboard/` prefix (see instructions above)

### Apple App Store
- [ ] Register Apple Pay merchant ID (`merchant.ai.outfi.app`)
- [ ] Add Apple Pay capability in Xcode
- [ ] Configure merchant ID in Stripe Dashboard

### Stripe (Production)
- [ ] Set up production webhook → `https://outfi.ai/api/v1/payments/webhook/`
- [ ] Enable Apple Pay in Stripe Dashboard
- [ ] Switch to live keys

### Testing
- [x] PaymentIntent creation tested ($4.99 + $9.99)
- [x] Storyboard sharing tested (7 tests passed)
- [ ] Test full Apple Pay on real iPhone
- [ ] Test Gemini quota: verify free user hits 3/day, premium gets 25/day
- [ ] Test `/usage/` endpoint returns correct remaining counts
- [ ] Test Fashion Timeline, preferences, distance filter
- [ ] Load test with downsized config — verify stability under traffic

### Future Features
- [ ] **Design custom paywall UI** — waiting for design direction
- [ ] Onboarding flow — style/size/gender/location questionnaire
- [ ] Push notification delivery (FCM/APNs)
- [ ] Price alert background checker (Celery task)
- [ ] Cancel subscription UI in profile screen
- [ ] Fashion Timeline: image upload per day (camera/gallery)
- [ ] Fashion Timeline: outfit-of-the-week highlights
- [ ] Consider removing ML service entirely (Gemini replaces CLIP/BLIP)
- [ ] CloudFront CDN for S3 images
