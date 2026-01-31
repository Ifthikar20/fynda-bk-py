# Affiliate Network Setup Guide

## Quick Start

### 1. CJ Affiliate (Commission Junction)
**~3,000 brands** - Nike, Samsung, GoPro, Levi's

1. Go to [signup.cj.com](https://signup.cj.com/member/signup/publisher/)
2. Fill out publisher application (takes 1-3 days for approval)
3. Once approved, go to **Account → Web Services**
4. Generate your **Personal Access Token**
5. Copy your **Website ID** from Account Settings

```env
CJ_AFFILIATE_API_TOKEN=your-personal-access-token
CJ_WEBSITE_ID=your-website-id
```

---

### 2. Rakuten Advertising
**~2,500 retailers** - Walmart, Macy's, Sephora

1. Go to [rakutenadvertising.com](https://rakutenadvertising.com/publishers/)
2. Click "Become a Publisher"
3. Complete application (1-5 days approval)
4. After approval: **Links → Product Link API**
5. Generate API credentials

```env
RAKUTEN_API_TOKEN=your-api-token
RAKUTEN_SITE_ID=your-site-id
```

---

### 3. ShareASale
**~16,000 merchants** - Etsy, Reebok, Wayfair

1. Go to [shareasale.com/info/affiliates](https://www.shareasale.com/info/affiliates)
2. Click "Affiliate Sign Up"
3. Complete application (instant to 2 days)
4. After approval: **Tools → API**
5. Generate API credentials

```env
SHAREASALE_AFFILIATE_ID=your-affiliate-id
SHAREASALE_API_TOKEN=your-api-token
SHAREASALE_API_SECRET=your-api-secret
```

---

## After Setup

Once you have the tokens, update `/FB_APP/.env` and restart the Django server:

```bash
python manage.py runserver 8000
```

The services will automatically use your credentials to fetch products.

---

## Tips

- **Start with CJ** - easiest approval process
- **Rakuten** has the best big-box retailers (Walmart, Target)
- **ShareASale** has the most niche/boutique brands
- Applications are free - no cost to join
