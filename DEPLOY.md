# Deploy

How to ship Outfi to production. Two repos, two pipelines, one EC2 box.

```
                  ┌──────────────────────── EC2 (Ubuntu) ─────────────────┐
git push          │                                                       │
  │               │  /opt/outfi  ── docker compose ──┐                    │
  ├─► FB_APP ─────┤      api · db · redis · nginx ◄──┘  (deploy.sh)       │
  │   (this repo) │                                                       │
  │               │  /var/www/frontend/dist  ◄── scp from GitHub Actions  │
  └─► outfi-frontend-vue                                                  │
      (separate repo)                                                     │
                  └───────────────────────────────────────────────────────┘
```

- **Backend** (`FB_APP`) — manual: push → SSH → run `deploy/deploy.sh`.
- **Frontend** (`outfi-frontend-vue`) — automatic: push → GitHub Actions builds & SCPs `dist/` to EC2.

> **Order matters when you change both.** Backend first, frontend second. Otherwise the SPA will hit endpoints that don't exist yet.

---

## 1. Backend (`FB_APP`)

### Pre-flight (one time)
- EC2 box has run `deploy/setup-ec2.sh` once (Docker, swap, ufw, fail2ban).
- `/opt/outfi` is a clone of this repo.
- `/opt/outfi/.env.production` exists and is filled in (see `.env.production.example`).
- DNS for `api.outfi.ai` (and any other subdomains in `nginx/conf.d/api.conf`) points at the EC2 elastic IP.
- TLS certs are in place (`deploy/ssl-setup.sh` for the initial Let's Encrypt issue).

### Deploy

From your laptop:

```bash
git push origin main
```

Then SSH to EC2 and run:

```bash
ssh ubuntu@<EC2_HOST>
cd /opt/outfi
./deploy/deploy.sh
```

What `deploy.sh` does (see the script for details):

1. Verifies `.env.production` and Docker are available.
2. `git fetch && git pull origin main` if there are new commits.
3. `docker compose -f docker-compose.prod.yml --env-file .env.production build --parallel`
4. `docker compose ... down --remove-orphans`
5. `docker compose ... up -d`
6. Waits 10 s, then runs migrations and `collectstatic` inside the `api` container.
7. Hits `http://localhost:8000/api/health/` as a smoke test.

### Verify

```bash
# from EC2
docker compose -f docker-compose.prod.yml ps
curl -sf https://api.outfi.ai/api/v1/health/ && echo OK
```

All five containers (`api`, `db`, `redis`, `nginx`, `celery` if enabled) should be `Up (healthy)`.

---

## 2. Frontend (`outfi-frontend-vue`)

The frontend lives in its own repo at `Ifthikar20/outfi-frontend-vue` (cloned to `frontend/` here, and **gitignored** from `FB_APP` — see `.gitignore`).

### Deploy

```bash
cd frontend
git push origin main
```

That's it. `.github/workflows/deploy.yml` runs on every push to `main`:

1. `npm ci`
2. `npm run build` with `VITE_API_URL=https://api.outfi.ai` baked in
   - ⚠️ The hostname is hardcoded in the workflow YAML, not a GitHub `vars` value. If the API ever moves, edit `.github/workflows/deploy.yml` and push — there's no other source of truth.
3. SCPs `dist/` to EC2 using the `EC2_SSH_KEY` GitHub secret.

### Verify

- Watch the run at `https://github.com/Ifthikar20/outfi-frontend-vue/actions`.
- Hard-refresh the production URL (`Cmd-Shift-R`). Check the network tab — it should be loading hashed asset filenames newer than the previous deploy.

---

## 3. Combined backend + frontend deploy (the usual case)

When a feature touches both repos (e.g. a new endpoint + the page that consumes it):

```bash
# 1. Backend first
cd ~/FB_APP
git push origin main
ssh ubuntu@<EC2_HOST> 'cd /opt/outfi && ./deploy/deploy.sh'

# 2. Then frontend
cd ~/FB_APP/frontend
git push origin main          # Actions handles the rest
```

After the frontend Action finishes, hard-refresh the prod URL.

---

## 4. Common ops

### Tail logs
```bash
ssh ubuntu@<EC2_HOST>
cd /opt/outfi
./deploy/logs.sh            # all services
./deploy/logs.sh api        # just one
```

### One-off Django command
```bash
docker compose -f docker-compose.prod.yml exec api python manage.py <command>
```

### Promote a user to staff
Required to access the analytics dashboard (`/internal/analytics/` or the SPA `/analytics` route).

```bash
docker compose -f docker-compose.prod.yml exec api python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
u = U.objects.get(email='YOUR@EMAIL.COM')
u.is_staff = True
u.save()
print('promoted', u.email)
"
```

> The Vue SPA reads `is_staff` from the user object stored after login. **A user that was promoted while already logged in must log out and back in** for the `/analytics` link to unlock.

### Create a fresh superuser
```bash
docker compose -f docker-compose.prod.yml exec api python manage.py createsuperuser
```

### Run migrations only
```bash
docker compose -f docker-compose.prod.yml exec api python manage.py migrate
```

### Stop everything
```bash
./deploy/stop.sh
```

### Rollback
There's no automated rollback. Procedure:

```bash
ssh ubuntu@<EC2_HOST>
cd /opt/outfi
git log --oneline -10                    # find the last good SHA
git checkout <good-sha>
./deploy/deploy.sh                       # rebuilds at that SHA
# when stable, fast-forward main on origin or revert the bad commit
```

For the frontend, re-run a previous successful Action via the GitHub UI ("Re-run jobs"), or `git revert` and push.

---

## 5. First-time EC2 setup

Only needed once per box. Documented in `deploy/setup-ec2.sh` — run it as root on a fresh Ubuntu instance:

```bash
sudo bash deploy/setup-ec2.sh
```

It installs Docker, configures `ufw` (22/80/443), creates `/opt/outfi`, sets up 2 GB swap, and installs `fail2ban`. After it finishes:

1. `git clone <FB_APP repo> /opt/outfi`
2. `cp .env.production.example .env.production` and fill it in
3. `bash deploy/ssl-setup.sh` to get Let's Encrypt certs
4. `bash deploy/deploy.sh` for the first deploy

Set the GitHub secrets `EC2_HOST` and `EC2_SSH_KEY` in the `outfi-frontend-vue` repo so its Action can SCP to the box.

---

## 6. Smoke tests after any deploy

```bash
# Health
curl -sf https://api.outfi.ai/api/v1/health/

# Public surface returns JSON, not HTML
curl -sf https://api.outfi.ai/ | head -c 200

# Analytics endpoint refuses anonymous (should be 401)
curl -s -o /dev/null -w "%{http_code}\n" https://api.outfi.ai/api/auth/analytics/data/
```

Then in a browser:

1. Sign in to the SPA as a staff user.
2. Visit `/analytics`. You should see stat tiles populated and the 30-day signup chart.
3. Sign in as a non-staff user. `/analytics` should bounce to `/`.

If the page renders empty or errors, check:
- Browser console for the actual API URL it's calling — make sure it matches your live API host.
- `./deploy/logs.sh api` for `403` or `401` lines.

---

## 7. Things that bite

- **Frontend deploy targets the wrong API host.** `.github/workflows/deploy.yml` hard-codes `VITE_API_URL` (currently `https://api.outfi.ai`) and the verify step curls `https://outfi.ai`. Both are literal strings — there's no `vars`/`secrets` indirection. Update both lines together if either domain moves.
- **Migrations fail mid-deploy.** `deploy.sh` runs them after containers are up — if they fail, the API is up but talking to a partially-migrated DB. Fix the migration, push, re-run `deploy.sh`. Don't try to "patch" by editing the DB by hand.
- **Throttles look like bugs in dev.** `BotDetectionMiddleware` and `RateLimitMiddleware` will return 429 to repeated curl bursts. In dev this resets on server restart (LocMemCache); in prod it's per-IP and self-clears within a minute.
- **`is_staff` cached on the client.** The SPA stores `is_staff` from the login response. Promoting a user in the DB doesn't unlock the page until they log out and back in.
- **`/api/internal/` is a honeypot**, not a real path. Internal HTML analytics is at `/internal/analytics/` (no `/api/` prefix) on purpose. See `outfi/middleware/api_guard.py:41`.
