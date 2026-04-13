# Notification Setup TODO

## 1. Apple Push Notifications (APNs Key)

The code is fully deployed. You need to generate a key and add it to the server.

### Steps:
1. Go to https://developer.apple.com → sign in
2. Certificates, Identifiers & Profiles → **Keys** → click **+**
3. Name: "Outfi APNs" → check **Apple Push Notifications service (APNs)** → Continue → Register
4. **Download** the `.p8` file (one-time download only!)
5. Note the **Key ID** (10 characters shown on screen)
6. Note your **Team ID** (top-right of developer portal, or Membership → Team ID)

### Deploy to server:
```bash
# Copy the .p8 key to server
scp -i ~/.ssh/fynda-api-key.pem AuthKey_XXXXXXXXXX.p8 ubuntu@54.81.148.134:/home/ubuntu/fynda/certs/apns_key.p8

# SSH in and add env vars
ssh -i ~/.ssh/fynda-api-key.pem ubuntu@54.81.148.134
mkdir -p /home/ubuntu/fynda/certs

# Add to .env
echo "APNS_KEY_ID=XXXXXXXXXX" >> /home/ubuntu/fynda/.env
echo "APNS_TEAM_ID=YYYYYYYYYY" >> /home/ubuntu/fynda/.env
echo "APNS_KEY_PATH=/app/certs/apns_key.p8" >> /home/ubuntu/fynda/.env
echo "APNS_USE_SANDBOX=false" >> /home/ubuntu/fynda/.env

# Rebuild
cd /home/ubuntu/fynda
sudo docker compose -f docker-compose.prod.yml up -d --build api celery
```

### Also: Add certs volume to docker-compose.prod.yml
Under the `api` service volumes, add:
```yaml
- ./certs:/app/certs:ro
```
Same for the `celery` service.

### Xcode: Enable Push Notification capability
1. Open `ios/Runner.xcworkspace` in Xcode
2. Select Runner project → Runner target → Signing & Capabilities
3. Click **+ Capability** → **Push Notifications**
4. This registers the entitlement with Apple's provisioning system


## 2. AWS SES (Email Alerts)

Email service code is deployed but AWS credentials aren't set on the server.

### Steps:
1. Go to AWS Console → SES → Verify your sender email (noreply@outfi.ai)
2. Create SMTP credentials or use IAM access keys
3. Add to server .env:
```bash
echo "AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXX" >> /home/ubuntu/fynda/.env
echo "AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxx" >> /home/ubuntu/fynda/.env
echo "AWS_SES_REGION_NAME=us-east-1" >> /home/ubuntu/fynda/.env
```
4. Rebuild: `sudo docker compose -f docker-compose.prod.yml up -d --build api celery`


## 3. Open the App (Register Device Token)

After installing v1.0.1+17 (already done):
1. Open Outfi on your iPhone
2. iOS will prompt: "Outfi would like to send you notifications"
3. Tap **Allow**
4. The app sends the APNs device token to the backend
5. Verify: check `DeviceToken` table in admin or via shell


## How it all connects

```
User creates alert from product page
        ↓
Backend stores DealAlert in DB
        ↓
Celery task runs every 4 hours (check-deal-alerts)
        ↓
Searches marketplaces for matching deals
        ↓
Stores new matches in DealAlertMatch
        ↓
Sends collated EMAIL via AWS SES ← needs SES credentials
        ↓
Sends PUSH notification via APNs ← needs .p8 key
        ↓
User sees notification on iPhone lock screen
User sees "Triggered" badge in app → taps → sees matched deals
```
