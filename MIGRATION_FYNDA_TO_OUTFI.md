# Migration: outfi.shop → outfi.ai

## ✅ DONE — Server / Infrastructure

### 1. SSL Certificates
- Issued Let's Encrypt certs for `api.outfi.ai` + `blog.outfi.ai`
- Path: `/etc/letsencrypt/live/api.outfi.ai/`
- Expires: 2026-05-22 (auto-renew enabled)

### 2. Nginx (`nginx/conf.d/api.conf`)
- All `server_name` directives updated to `api.outfi.ai`, `blog.outfi.ai`, `outfi.ai`, `www.outfi.ai`
- SSL certs point to `api.outfi.ai` paths
- Added HTTPS (443) server block for `outfi.ai` (Cloudflare Full SSL)
- Removed `outfi.shop` redirect from default catch-all

### 3. Django `.env` on EC2 (`/home/ubuntu/outfi/.env`)
- `ALLOWED_HOSTS` → added `outfi.ai`, `www.outfi.ai`, `api.outfi.ai`, `blog.outfi.ai`
- `CORS_ALLOWED_ORIGINS` → added `https://outfi.ai`, `https://www.outfi.ai`

---

## ❌ STILL TODO — Frontend Code Replacements

These files still have `outfi` references that need to be changed:

### `frontend/index.html`
```
Line 5:  outfi-png-1.png → (keep, it's a filename)
Line 7:  <title>Outfi - Discover the Best Deals</title>  →  Outfi - Discover the Best Deals
Line 8:  "Outfi helps you discover..."  →  "Outfi helps you discover..."
Line 12: og:title "Outfi..."  →  "Outfi..."
```

### `frontend/src/components/HomePage.vue`
```
Line 21:   "Ask Outfi anything"  →  "Ask Outfi anything"
Line 307:  blog.outfi.com  →  blog.outfi.ai
Line 320:  instagram.com/outfi  →  instagram.com/outfi.ai
Line 321:  twitter.com/outfi  →  twitter.com/outfi_ai
Line 322:  tiktok.com/@outfi  →  tiktok.com/@outfi.ai
Line 323:  pinterest.com/outfi  →  pinterest.com/outfiai
Line 952:  'Outfi' fallback  →  'Outfi'
Line 1031: 'Outfi' fallback  →  'Outfi'
```

### `frontend/src/components/Footer.vue`
```
Line 24:  blog.outfi.com  →  blog.outfi.ai
Line 37:  instagram.com/outfi  →  instagram.com/outfi.ai
Line 38:  twitter.com/outfi  →  twitter.com/outfi_ai
Line 39:  tiktok.com/@outfi  →  tiktok.com/@outfi.ai
Line 40:  pinterest.com/outfi  →  pinterest.com/outfiai
Lines 53-70: same social links (icon versions)
```

### `frontend/src/components/pages/ContactPage.vue`
```
Line 55:  hello@outfi.com  →  hello@outfi.ai
Line 62:  support@outfi.com  →  support@outfi.ai
Line 69:  press@outfi.com  →  press@outfi.ai
Lines 75-95: social links (instagram/twitter/tiktok/pinterest)
```

### `frontend/src/components/pages/TermsPage.vue`
```
Line 14:  "using Outfi"  →  "using Outfi"
Line 22:  "Outfi is a deal aggregation"  →  "Outfi is a deal aggregation"
Line 65:  "owned by Outfi"  →  "owned by Outfi"
Line 82:  "Outfi shall not"  →  "Outfi shall not"
Line 108: legal@outfi.com  →  legal@outfi.ai
```

### `frontend/src/components/pages/AboutPage.vue`
```
Line 13:  "Outfi is revolutionizing"  →  "Outfi is revolutionizing"
Line 23:  "Outfi changes that"  →  "Outfi changes that"
```

### `frontend/src/components/pages/HelpCenterPage.vue`
```
Line 56:  support@outfi.com  →  support@outfi.ai
```

---

## ⚠️ DO NOT CHANGE — Internal Keys (localStorage)

These are internal storage keys. Changing them would break existing users' sessions/data:

- `outfi_tokens`, `outfi_user` (tokenStorage.js)
- `outfi_cookie_consent`, `outfi_func_*`, `outfi_analytics` (cookieService.js)
- `outfi_utm` (utmService.js)
- `outfi_device_id`, `outfi_distinct_id`, `outfi_session_id`, `outfi_events` (analyticsService.js)
- `outfiCloset`, `outfiCompare`, `outfiViewProduct` (ProductDetailPage, NavBar, HomePage)
- `outfi_ai_mode`, `outfi_search_count` (HomePage)
- `outfi_storyboards` (StoryboardPage)
- `outfiProduct_*` (SharedStoryboardPage)

---

## Quick Command to Apply All Frontend Changes

```bash
cd /Users/ifthikaraliseyed/FB_APP/frontend

# index.html
sed -i '' 's/Outfi - Discover the Best Deals/Outfi - Discover the Best Deals/g' index.html
sed -i '' 's/Outfi helps you discover/Outfi helps you discover/g' index.html
sed -i '' 's/content="Outfi/content="Outfi/g' index.html

# All .vue and .js files — user-facing text
find src -name '*.vue' -o -name '*.js' | xargs sed -i '' \
  's/blog\.outfi\.com/blog.outfi.ai/g;
   s/instagram\.com\/outfi/instagram.com\/outfi.ai/g;
   s/twitter\.com\/outfi/twitter.com\/outfi_ai/g;
   s/tiktok\.com\/@outfi/tiktok.com\/@outfi.ai/g;
   s/pinterest\.com\/outfi/pinterest.com\/outfiai/g;
   s/hello@outfi\.com/hello@outfi.ai/g;
   s/support@outfi\.com/support@outfi.ai/g;
   s/press@outfi\.com/press@outfi.ai/g;
   s/legal@outfi\.com/legal@outfi.ai/g;
   s/Ask Outfi anything/Ask Outfi anything/g;
   s/using Outfi/using Outfi/g;
   s/Outfi is a deal/Outfi is a deal/g;
   s/owned by Outfi/owned by Outfi/g;
   s/Outfi shall/Outfi shall/g;
   s/Outfi is revolutionizing/Outfi is revolutionizing/g;
   s/Outfi changes that/Outfi changes that/g'

# Merchant name fallback
sed -i '' "s/|| 'Outfi'/|| 'Outfi'/g" src/components/HomePage.vue
```
