# Outfi Mobile API — Flutter Integration Guide

> **Base URL:** `https://api.outfi.ai/api/mobile/`
> **Auth:** Bearer JWT tokens via `Authorization: Bearer <access_token>` header
> **Content-Type:** `application/json` (except image upload which uses `multipart/form-data`)

---

## Architecture Overview

```
┌─────────────────────┐
│   Flutter App        │
│  (iOS / Android)     │
└──────────┬──────────┘
           │  HTTPS + JWT
           ▼
┌─────────────────────┐
│  Django REST API     │
│  /api/mobile/*       │
├─────────────────────┤
│  Orchestrator        │──► CJ Affiliate API
│  (Deal Search)       │──► Rakuten API
│                      │──► ShareASale API
│                      │──► Amazon RapidAPI (cached, 429 fallback)
├─────────────────────┤
│  ML Service (BLIP)   │──► Image → Search Queries
│  (Fashion CLIP)      │
├─────────────────────┤
│  OpenAI Vision       │──► Fallback image analysis
│  (Fallback)          │
└─────────────────────┘
```

---

## 🔑 Authentication

### Email Login
```
POST /api/mobile/auth/login/
```

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "device_id": "unique-device-uuid",
  "platform": "ios",
  "app_version": "1.0.0",
  "push_token": "fcm-or-apns-token"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "device_id": "uuid",
  "preferences": {
    "push_enabled": true,
    "theme": "system",
    "currency": "USD",
    "language": "en",
    "default_sort": "relevance"
  }
}
```

### Email Registration
```
POST /api/mobile/auth/register/
```

**Request:** Same as login + `first_name`, `last_name` (optional). Password min 8 chars.

### OAuth (Google / Apple)
```
POST /api/mobile/auth/oauth/
```

**Request:**
```json
{
  "provider": "google",
  "code": "authorization_code_from_oauth_flow",
  "redirect_uri": "com.fynda.app:/oauth/callback",
  "device_id": "unique-device-uuid",
  "platform": "ios",
  "push_token": "fcm-token"
}
```

For **Apple Sign-In**, also include:
```json
{
  "provider": "apple",
  "code": "auth_code",
  "id_token": "apple_identity_token",
  "user": {"name": {"firstName": "John", "lastName": "Doe"}},
  "device_id": "...",
  "platform": "ios"
}
```

**Response:** Same format as email login response.

> **Flutter Implementation:** Use `google_sign_in` and `sign_in_with_apple` packages. Send the auth code to this endpoint, which handles token exchange server-side.

### Logout
```
POST /api/mobile/auth/logout/
Authorization: Bearer <token>
```

**Request:**
```json
{
  "device_id": "unique-device-uuid"
}
```

### Token Refresh
```
POST /api/auth/token/refresh/
```

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response:**
```json
{
  "access": "eyJ_new_access_token..."
}
```

---

## 📸 Core Flow: Photo → Deals

This is the **primary Flutter use case**. User takes a photo of clothing → app uploads it → backend identifies the item → returns matching deals from all marketplaces.

### Image Search
```
POST /api/mobile/deals/image-search/
Content-Type: multipart/form-data
```

**Request:**
- `image`: JPEG/PNG/WebP file (max 10MB)

**Response (200):**
```json
{
  "extracted": {
    "caption": "blue denim jacket with brass buttons",
    "colors": {"primary": "blue", "secondary": "gold"},
    "textures": ["denim", "woven"],
    "category": "jackets"
  },
  "search_queries": ["blue denim jacket", "brass button jean jacket"],
  "deals": [
    {
      "id": "cj_12345",
      "title": "Levi's Denim Trucker Jacket",
      "price": "89.99",
      "original_price": "129.99",
      "discount": 31,
      "currency": "USD",
      "image": "https://...",
      "source": "CJ Affiliate",
      "url": "https://...",
      "rating": 4.5,
      "in_stock": true,
      "is_saved": false
    }
  ],
  "total": 15,
  "search_time_ms": 2340,
  "quota_warning": "Some results may be limited right now."
}
```

**Processing Pipeline:**
1. Image resized to 800px max dimension (server-side)
2. **ML Service (BLIP/Fashion CLIP)** on EC2 analyzes the image
3. If ML fails → **OpenAI Vision** fallback
4. Generated search queries run in parallel across all affiliates
5. Results deduplicated and returned with mobile-optimized compact payload

> **Flutter Tip:** Use `image_picker` for camera/gallery. Compress to ~800px before upload to speed transfer.

### If image cannot be identified:
```json
{
  "extracted": {},
  "search_queries": [],
  "deals": [],
  "total": 0,
  "search_time_ms": 1200,
  "message": "Could not identify product. Try a clearer image."
}
```

---

## 🔍 Text Search
```
POST /api/mobile/deals/search/
```

**Request:**
```json
{
  "query": "nike air force 1",
  "min_price": 50,
  "max_price": 200,
  "sort": "price_low",
  "limit": 20
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `query` | string | ✅ | — | Max 500 chars |
| `min_price` | decimal | ❌ | — | Filter: minimum price |
| `max_price` | decimal | ❌ | — | Included in query for NLP parsing |
| `sort` | string | ❌ | `relevance` | `relevance`, `price_low`, `price_high`, `rating`, `newest` |
| `limit` | int | ❌ | `20` | Max 50 |

**Response:** Same deal array format as image search.

### Trending Deals
```
GET /api/mobile/deals/?limit=20&sort=price_low
```

Returns featured/trending deals. No auth required.

---

## ⚠️ Quota Warning

When the Amazon RapidAPI quota is exceeded, responses include:
```json
{
  "deals": [...],
  "quota_warning": "Some marketplace results may be limited right now. Please try again later."
}
```

**Flutter Handling:** Check for `quota_warning` field and show a subtle `SnackBar` or info banner. Other marketplace results still flow normally — only Amazon is affected.

---

## ❤️ Favorites
```
GET /api/mobile/favorites/           → List saved deals (max 100)
POST /api/mobile/favorites/          → Save a deal
DELETE /api/mobile/favorites/{deal_id}/  → Unsave a deal
```

**Save a deal:**
```json
{
  "deal_id": "cj_12345",
  "deal_data": {
    "title": "Levi's Jacket",
    "price": 89.99,
    "image_url": "https://...",
    "source": "CJ",
    "url": "https://..."
  }
}
```

> **Important:** `deal_data` is stored server-side so favorites persist even if the deal disappears from search results. The `is_saved: true` flag on deal objects lets you show a filled heart icon inline.

---

## 🔔 Price Alerts
```
GET /api/mobile/alerts/              → List alerts (?status=active)
POST /api/mobile/alerts/             → Create alert
GET /api/mobile/alerts/{id}/         → Get alert detail
PATCH /api/mobile/alerts/{id}/       → Update alert
DELETE /api/mobile/alerts/{id}/      → Delete alert
```

**Create an alert:**
```json
{
  "product_query": "airpods pro",
  "product_name": "Apple AirPods Pro 2",
  "product_image": "https://...",
  "product_url": "https://...",
  "target_price": "199.99",
  "original_price": "249.99",
  "currency": "USD"
}
```

**Response includes computed fields:**
```json
{
  "id": "uuid",
  "status": "active",
  "current_price": "229.99",
  "lowest_price": "219.99",
  "price_drop_percent": 8.0,
  "last_checked_at": "2026-02-08T15:00:00Z",
  "triggered_at": null
}
```

---

## 🎨 Fashion Storyboard
```
GET /api/mobile/storyboard/              → List my storyboards
POST /api/mobile/storyboard/             → Create storyboard
GET /api/mobile/storyboard/{token}/      → View shared storyboard (public)
```

**Create:**
```json
{
  "title": "Summer Outfit Inspo",
  "storyboard_data": {
    "items": [...],
    "layout": "grid",
    "background": "#fafafa"
  },
  "expires_in_days": 30
}
```

**Response:**
```json
{
  "token": "abc123xyz",
  "share_url": "https://outfi.ai/storyboard/abc123xyz",
  "expires_at": "2026-03-10T15:00:00Z"
}
```

---

## 📱 Device Management
```
GET /api/mobile/devices/                 → List active devices
POST /api/mobile/devices/                → Register/update device
PATCH /api/mobile/devices/{id}/          → Update push token
DELETE /api/mobile/devices/{id}/         → Unregister device
```

---

## ⚙️ User Preferences
```
GET /api/mobile/preferences/             → Get preferences
PATCH /api/mobile/preferences/           → Update preferences
```

**Fields:**
```json
{
  "push_enabled": true,
  "push_deals": true,
  "push_price_alerts": true,
  "push_weekly_digest": false,
  "theme": "system",
  "currency": "USD",
  "language": "en",
  "default_sort": "relevance",
  "show_sold_items": false,
  "preferred_sources": ["CJ", "Rakuten"],
  "save_search_history": true,
  "anonymous_analytics": true
}
```

---

## 🔄 Offline Sync
```
GET /api/mobile/sync/                    → Get sync state
POST /api/mobile/sync/                   → Pull changes since last sync
```

**Request:**
```json
{
  "entity_types": ["favorites", "alerts", "preferences"],
  "sync_tokens": {
    "favorites": "last_token_from_previous_sync",
    "alerts": "another_token"
  },
  "full_sync": false
}
```

**Response:**
```json
{
  "favorites": {
    "items": [...],
    "total": 12,
    "sync_token": "new_token"
  },
  "alerts": {
    "items": [...],
    "total": 3,
    "sync_token": "new_token"
  },
  "preferences": { ... },
  "sync_tokens": {
    "favorites": "new_token",
    "alerts": "new_token"
  },
  "synced_at": "2026-02-08T15:00:00Z",
  "has_conflicts": false
}
```

> **Flutter Implementation:** Store sync tokens in `shared_preferences`. On app launch, call sync with stored tokens to get incremental updates. Use `full_sync: true` for initial setup or recovery.

---

## 🏥 Health Check
```
GET /api/mobile/health/?platform=ios
```

**Response:**
```json
{
  "status": "ok",
  "server_time": "2026-02-08T15:00:00Z",
  "min_app_version": "1.0.0",
  "force_update": false,
  "maintenance": false,
  "message": ""
}
```

> **Flutter:** Call on app startup. If `force_update: true`, show a blocking modal. If `maintenance: true`, show maintenance screen.

---

## Error Handling

All errors follow a consistent format:
```json
{
  "error": "Human-readable error message"
}
```

| Status Code | Meaning |
|-------------|---------|
| `400` | Bad request (validation error) |
| `401` | Invalid / expired token |
| `403` | Account disabled |
| `404` | Resource not found |
| `410` | Resource expired (storyboard) |
| `500` | Server error |

**Flutter pattern:**
```dart
if (response.statusCode == 401) {
  // Try token refresh → if fails, redirect to login
  final refreshed = await refreshToken();
  if (!refreshed) navigateToLogin();
}
```

---

## Recommended Flutter Packages

| Package | Purpose |
|---------|---------|
| `dio` | HTTP client with interceptors for JWT refresh |
| `image_picker` | Camera and gallery access |
| `shared_preferences` | Store tokens and sync cursors |
| `google_sign_in` | Google OAuth |
| `sign_in_with_apple` | Apple Sign-In |
| `flutter_secure_storage` | Secure token storage |
| `cached_network_image` | Image caching for deal thumbnails |
| `hive` | Local database for offline deal cache |

---

## Complete Endpoint Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health/` | GET | ❌ | App health + version check |
| `/auth/login/` | POST | ❌ | Email login + device bind |
| `/auth/register/` | POST | ❌ | Email register + device bind |
| `/auth/logout/` | POST | ✅ | Logout + deactivate device |
| `/auth/oauth/` | POST | ❌ | Google/Apple login + device bind |
| `/devices/` | GET/POST | ✅ | List/register devices |
| `/devices/{id}/` | PATCH/DELETE | ✅ | Update/remove device |
| `/preferences/` | GET/PATCH | ✅ | User preferences |
| `/sync/` | GET/POST | ✅ | Offline sync |
| `/deals/` | GET | ❌ | Trending deals |
| `/deals/search/` | POST | ❌ | Text search |
| `/deals/image-search/` | POST | ❌ | **Photo → deals** |
| `/alerts/` | GET/POST | ✅ | Price alerts |
| `/alerts/{id}/` | GET/PATCH/DELETE | ✅ | Single alert |
| `/favorites/` | GET/POST | ✅ | Saved deals |
| `/favorites/{deal_id}/` | DELETE | ✅ | Unsave deal |
| `/storyboard/` | GET/POST | ✅ | Fashion storyboards |
| `/storyboard/{token}/` | GET | ❌ | View shared storyboard |
