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
- [x] `mobile/0003_add_location_style_preferences` — already applied
- [ ] Run `python manage.py migrate` to apply `payments/0001_initial`

### Stripe Setup
- [ ] Create Stripe account at https://stripe.com
- [ ] Get API keys and add to `.env`:
  ```
  STRIPE_PUBLISHABLE_KEY=pk_live_...
  STRIPE_SECRET_KEY=sk_live_...
  STRIPE_WEBHOOK_SECRET=whsec_...
  ```
- [ ] Set up Stripe webhook endpoint pointing to `https://outfi.ai/api/v1/payments/webhook/`
- [ ] Configure webhook events: `payment_intent.succeeded`, `payment_intent.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`
- [ ] Enable Apple Pay in Stripe Dashboard → Settings → Payment Methods

### Flutter / Mobile App
- [ ] Add `flutter_stripe` package for Apple Pay sheet integration
- [ ] Build subscription/upgrade screen (show plans, trigger Apple Pay)
- [ ] Call `POST /payments/subscribe/` → use `client_secret` with Stripe SDK
- [ ] Handle payment success → refresh subscription status
- [ ] Add `POST /payments/restore/` call on app launch for returning users
- [ ] Add location/style preference UI in settings screen
- [ ] Add distance filter UI for marketplace results
- [ ] Update storyboard flows — add share button, handle `is_public` toggle
- [ ] Flutter submodule update

### Apple App Store
- [ ] Register app for Apple Pay merchant ID in Apple Developer portal
- [ ] Add Apple Pay capability in Xcode
- [ ] Configure merchant ID in Stripe Dashboard

### Testing
- [ ] Test full Apple Pay flow with Stripe test keys (`pk_test_...` / `sk_test_...`)
- [ ] Test webhook handling with `stripe listen --forward-to localhost:8000/api/v1/payments/webhook/`
- [ ] Test premium enforcement — verify free users hit 5/day limit, premium get 50/day
- [ ] Test storyboard sharing — public view by token, private board returns 404
- [ ] Test background remover with small images (< 64px)
- [ ] Test search with saved location preferences

### Future Features
- [ ] Onboarding flow — questionnaire for style/size/gender/location
- [ ] Push notification delivery (FCM/APNs integration)
- [ ] Price alert background checker (Celery task)
- [ ] Stripe Customer Portal for self-service billing management
