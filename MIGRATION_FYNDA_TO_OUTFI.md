# Migration: fynda.shop → outfi.ai

## ✅ DONE — Server / Infrastructure

### 1. SSL Certificates
- Issued Let's Encrypt certs for `api.outfi.ai` + `blog.outfi.ai`
- Path: `/etc/letsencrypt/live/api.outfi.ai/`
- Expires: 2026-05-22 (auto-renew enabled)

### 2. Nginx (`nginx/conf.d/api.conf`)
- All `server_name` directives updated to `api.outfi.ai`, `blog.outfi.ai`, `outfi.ai`, `www.outfi.ai`
- SSL certs point to `api.outfi.ai` paths
- Added HTTPS (443) server block for `outfi.ai` (Cloudflare Full SSL)
- Removed `fynda.shop` redirect from default catch-all

### 3. Django `.env` on EC2 (`/home/ubuntu/fynda/.env`)
- `ALLOWED_HOSTS` → added `outfi.ai`, `www.outfi.ai`, `api.outfi.ai`, `blog.outfi.ai`
- `CORS_ALLOWED_ORIGINS` → added `https://outfi.ai`, `https://www.outfi.ai`

---

## ❌ STILL TODO — Frontend Code Replacements

These files still have `fynda` references that need to be changed:

### `frontend/index.html`
```
Line 5:  fynda-png-1.png → (keep, it's a filename)
Line 7:  <title>Fynda - Discover the Best Deals</title>  →  Outfi - Discover the Best Deals
Line 8:  "Fynda helps you discover..."  →  "Outfi helps you discover..."
Line 12: og:title "Fynda..."  →  "Outfi..."
```

### `frontend/src/components/HomePage.vue`
```
Line 21:   "Ask Fynda anything"  →  "Ask Outfi anything"
Line 307:  blog.fynda.com  →  blog.outfi.ai
Line 320:  instagram.com/fynda  →  instagram.com/outfi.ai
Line 321:  twitter.com/fynda  →  twitter.com/outfi_ai
Line 322:  tiktok.com/@fynda  →  tiktok.com/@outfi.ai
Line 323:  pinterest.com/fynda  →  pinterest.com/outfiai
Line 952:  'Fynda' fallback  →  'Outfi'
Line 1031: 'Fynda' fallback  →  'Outfi'
```

### `frontend/src/components/Footer.vue`
```
Line 24:  blog.fynda.com  →  blog.outfi.ai
Line 37:  instagram.com/fynda  →  instagram.com/outfi.ai
Line 38:  twitter.com/fynda  →  twitter.com/outfi_ai
Line 39:  tiktok.com/@fynda  →  tiktok.com/@outfi.ai
Line 40:  pinterest.com/fynda  →  pinterest.com/outfiai
Lines 53-70: same social links (icon versions)
```

### `frontend/src/components/pages/ContactPage.vue`
```
Line 55:  hello@fynda.com  →  hello@outfi.ai
Line 62:  support@fynda.com  →  support@outfi.ai
Line 69:  press@fynda.com  →  press@outfi.ai
Lines 75-95: social links (instagram/twitter/tiktok/pinterest)
```

### `frontend/src/components/pages/TermsPage.vue`
```
Line 14:  "using Fynda"  →  "using Outfi"
Line 22:  "Fynda is a deal aggregation"  →  "Outfi is a deal aggregation"
Line 65:  "owned by Fynda"  →  "owned by Outfi"
Line 82:  "Fynda shall not"  →  "Outfi shall not"
Line 108: legal@fynda.com  →  legal@outfi.ai
```

### `frontend/src/components/pages/AboutPage.vue`
```
Line 13:  "Fynda is revolutionizing"  →  "Outfi is revolutionizing"
Line 23:  "Fynda changes that"  →  "Outfi changes that"
```

### `frontend/src/components/pages/HelpCenterPage.vue`
```
Line 56:  support@fynda.com  →  support@outfi.ai
```

---

## ⚠️ DO NOT CHANGE — Internal Keys (localStorage)

These are internal storage keys. Changing them would break existing users' sessions/data:

- `fynda_tokens`, `fynda_user` (tokenStorage.js)
- `fynda_cookie_consent`, `fynda_func_*`, `fynda_analytics` (cookieService.js)
- `fynda_utm` (utmService.js)
- `fynda_device_id`, `fynda_distinct_id`, `fynda_session_id`, `fynda_events` (analyticsService.js)
- `fyndaCloset`, `fyndaCompare`, `fyndaViewProduct` (ProductDetailPage, NavBar, HomePage)
- `fynda_ai_mode`, `fynda_search_count` (HomePage)
- `fynda_storyboards` (StoryboardPage)
- `fyndaProduct_*` (SharedStoryboardPage)

---

## Quick Command to Apply All Frontend Changes

```bash
cd /Users/ifthikaraliseyed/FB_APP/frontend

# index.html
sed -i '' 's/Fynda - Discover the Best Deals/Outfi - Discover the Best Deals/g' index.html
sed -i '' 's/Fynda helps you discover/Outfi helps you discover/g' index.html
sed -i '' 's/content="Fynda/content="Outfi/g' index.html

# All .vue and .js files — user-facing text
find src -name '*.vue' -o -name '*.js' | xargs sed -i '' \
  's/blog\.fynda\.com/blog.outfi.ai/g;
   s/instagram\.com\/fynda/instagram.com\/outfi.ai/g;
   s/twitter\.com\/fynda/twitter.com\/outfi_ai/g;
   s/tiktok\.com\/@fynda/tiktok.com\/@outfi.ai/g;
   s/pinterest\.com\/fynda/pinterest.com\/outfiai/g;
   s/hello@fynda\.com/hello@outfi.ai/g;
   s/support@fynda\.com/support@outfi.ai/g;
   s/press@fynda\.com/press@outfi.ai/g;
   s/legal@fynda\.com/legal@outfi.ai/g;
   s/Ask Fynda anything/Ask Outfi anything/g;
   s/using Fynda/using Outfi/g;
   s/Fynda is a deal/Outfi is a deal/g;
   s/owned by Fynda/owned by Outfi/g;
   s/Fynda shall/Outfi shall/g;
   s/Fynda is revolutionizing/Outfi is revolutionizing/g;
   s/Fynda changes that/Outfi changes that/g'

# Merchant name fallback
sed -i '' "s/|| 'Fynda'/|| 'Outfi'/g" src/components/HomePage.vue
```
