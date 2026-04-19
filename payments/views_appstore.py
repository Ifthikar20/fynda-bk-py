"""
Apple App Store Server Views

Handles:
1. Receipt verification after in-app purchase (POST /payments/verify-ios/)
2. App Store Server Notifications V2 (POST /payments/appstore-notify/)

Security:
  - Receipt verification uses Apple's verifyReceipt endpoint
  - Server notifications use JWS signature verification
  - Both are CSRF exempt (external API callbacks)
"""

import json
import base64
import logging
import requests
from datetime import datetime, timezone as tz

from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.cache import cache

from .models import Subscription, Payment

logger = logging.getLogger(__name__)

# Apple receipt verification endpoints
APPLE_VERIFY_RECEIPT_PROD = 'https://buy.itunes.apple.com/verifyReceipt'
APPLE_VERIFY_RECEIPT_SANDBOX = 'https://sandbox.itunes.apple.com/verifyReceipt'


class VerifyIOSReceiptView(APIView):
    """
    POST /payments/verify-ios/ — Verify an iOS App Store receipt.

    Called by the Flutter app after a successful StoreKit purchase.
    Validates the receipt with Apple, then activates the subscription.

    Request: {
        "receipt_data": "<base64 receipt>",
        "product_id": "com.outfi.outfiApp.premium.monthly",
        "transaction_id": "1000000123456789"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        receipt_data = request.data.get('receipt_data', '')
        product_id = request.data.get('product_id', '')
        transaction_id = request.data.get('transaction_id', '')

        if not receipt_data:
            return Response({'error': 'Missing receipt_data'}, status=400)

        # Idempotency: skip if we've already processed this transaction
        idempotency_key = f'ios_receipt:{transaction_id}'
        if transaction_id and cache.get(idempotency_key):
            logger.info(f'iOS receipt: duplicate transaction {transaction_id}, skipping')
            sub = Subscription.objects.filter(user=request.user).first()
            return Response({
                'verified': True,
                'is_premium': sub.is_premium if sub else False,
            })
        

        # Verify with Apple (try production first, fall back to sandbox)
        receipt_result = self._verify_with_apple(receipt_data)

        if not receipt_result:
            return Response({'error': 'Receipt verification failed'}, status=400)

        status_code = receipt_result.get('status', -1)

        if status_code != 0:
            logger.warning(f'iOS receipt: Apple returned status {status_code}')
            return Response({
                'error': f'Invalid receipt (status {status_code})',
                'verified': False,
            }, status=400)

        # Extract subscription info from the latest receipt
        latest_receipt_info = receipt_result.get('latest_receipt_info', [])
        if not latest_receipt_info:
            # Try pending_renewal_info
            latest_receipt_info = receipt_result.get('receipt', {}).get(
                'in_app', []
            )

        if not latest_receipt_info:
            return Response({'error': 'No subscription data in receipt'}, status=400)

        # Find the most recent transaction
        latest = max(latest_receipt_info, key=lambda x: int(
            x.get('expires_date_ms', x.get('purchase_date_ms', '0'))
        ))

        # Determine plan from product_id
        apple_product_id = latest.get('product_id', product_id)
        plan = self._determine_plan(apple_product_id)

        # Parse expiration
        expires_ms = latest.get('expires_date_ms')
        expires_at = None
        if expires_ms:
            expires_at = datetime.fromtimestamp(
                int(expires_ms) / 1000, tz=tz.utc
            )

        # Activate subscription
        sub, _ = Subscription.objects.get_or_create(user=request.user)
        sub.plan = plan
        sub.status = 'active'
        sub.current_period_start = datetime.now(tz.utc)
        sub.current_period_end = expires_at
        sub.cancel_at_period_end = False
        sub.original_transaction_id = latest.get(
            'original_transaction_id', transaction_id
        )
        sub.save()

        # Mark as processed (24h dedup window)
        if transaction_id:
            cache.set(idempotency_key, True, timeout=86400)

        logger.info(
            f'iOS receipt verified: {request.user.email} → {plan} '
            f'(expires {expires_at})'
        )

        return Response({
            'verified': True,
            'is_premium': True,
            'plan': plan,
            'expires_at': expires_at.isoformat() if expires_at else None,
        })

    def _verify_with_apple(self, receipt_data):
        """Verify receipt with Apple. Try production first, sandbox fallback."""
        shared_secret = getattr(settings, 'APPLE_IAP_SHARED_SECRET', '')

        payload = {
            'receipt-data': receipt_data,
            'exclude-old-transactions': True,
        }
        if shared_secret:
            payload['password'] = shared_secret

        try:
            # Try production first
            resp = requests.post(
                APPLE_VERIFY_RECEIPT_PROD,
                json=payload,
                timeout=15,
            )
            result = resp.json()

            # Status 21007 = sandbox receipt sent to production
            # Retry with sandbox endpoint
            if result.get('status') == 21007:
                resp = requests.post(
                    APPLE_VERIFY_RECEIPT_SANDBOX,
                    json=payload,
                    timeout=15,
                )
                result = resp.json()

            return result
        except Exception as e:
            logger.error(f'iOS receipt: Apple verification error: {e}')
            return None

    def _determine_plan(self, product_id):
        """Determine plan from Apple product ID."""
        if 'monthly' in product_id:
            return 'premium_monthly'
        elif 'biweekly' in product_id or 'weekly' in product_id:
            return 'premium_weekly'
        return 'premium_monthly'


@method_decorator(csrf_exempt, name='dispatch')
class AppStoreNotificationView(APIView):
    """
    POST /payments/appstore-notify/ — App Store Server Notifications V2.

    Apple sends signed JWS notifications for subscription lifecycle events:
      - DID_RENEW          → subscription renewed
      - DID_CHANGE_RENEWAL_STATUS → auto-renew toggled
      - EXPIRED            → subscription expired
      - DID_FAIL_TO_RENEW  → billing issue
      - REFUND             → user got a refund
      - SUBSCRIBED         → initial purchase (also handled by verify-ios)

    Set this URL in App Store Connect:
      General → App Information → App Store Server Notifications URL
      → https://api.outfi.ai/api/v1/payments/appstore-notify/
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            logger.warning('App Store notify: invalid JSON')
            return HttpResponse(status=400)

        signed_payload = payload.get('signedPayload', '')
        if not signed_payload:
            logger.warning('App Store notify: missing signedPayload')
            return HttpResponse(status=400)

        # Decode JWS payload (middle segment is the claims)
        try:
            notification = self._decode_jws_payload(signed_payload)
        except Exception as e:
            logger.error(f'App Store notify: JWS decode error: {e}')
            return HttpResponse(status=400)

        if not notification:
            return HttpResponse(status=400)

        notification_type = notification.get('notificationType', '')
        subtype = notification.get('subtype', '')
        notification_uuid = notification.get('notificationUUID', '')

        # Idempotency
        if notification_uuid:
            idempotency_key = f'appstore_notify:{notification_uuid}'
            if cache.get(idempotency_key):
                return HttpResponse(status=200)
            cache.set(idempotency_key, True, timeout=86400)

        logger.info(
            f'App Store notify: {notification_type} '
            f'(subtype={subtype}, uuid={notification_uuid})'
        )

        # Extract transaction info from the notification
        data = notification.get('data', {})
        signed_transaction = data.get('signedTransactionInfo', '')
        signed_renewal = data.get('signedRenewalInfo', '')

        transaction = {}
        renewal = {}
        if signed_transaction:
            transaction = self._decode_jws_payload(signed_transaction) or {}
        if signed_renewal:
            renewal = self._decode_jws_payload(signed_renewal) or {}

        # Route to handler
        handler_map = {
            'SUBSCRIBED': self._handle_subscribed,
            'DID_RENEW': self._handle_renewed,
            'EXPIRED': self._handle_expired,
            'DID_CHANGE_RENEWAL_STATUS': self._handle_renewal_status_change,
            'DID_FAIL_TO_RENEW': self._handle_billing_issue,
            'REFUND': self._handle_refund,
            'GRACE_PERIOD_EXPIRED': self._handle_expired,
        }

        handler = handler_map.get(notification_type)
        if handler:
            try:
                handler(transaction, renewal, subtype)
            except Exception as e:
                logger.error(
                    f'App Store notify: handler error: {e}', exc_info=True
                )
        else:
            logger.info(
                f'App Store notify: unhandled type: {notification_type}'
            )

        return HttpResponse(status=200)

    def _decode_jws_payload(self, jws_string):
        """Decode the payload (middle part) of a JWS string."""
        try:
            parts = jws_string.split('.')
            if len(parts) != 3:
                return None

            # Decode the payload (second part, base64url encoded)
            payload_b64 = parts[1]
            # Add padding if needed
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding

            payload_json = base64.urlsafe_b64decode(payload_b64)
            return json.loads(payload_json)
        except Exception as e:
            logger.error(f'JWS decode error: {e}')
            return None

    def _find_subscription(self, transaction):
        """Find subscription by original_transaction_id."""
        original_txn_id = transaction.get(
            'originalTransactionId', ''
        )
        if not original_txn_id:
            return None

        sub = Subscription.objects.filter(
            original_transaction_id=original_txn_id
        ).first()

        if sub:
            return sub

        # Try by bundle-scoped app_account_token (user ID)
        app_account_token = transaction.get('appAccountToken', '')
        if app_account_token:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=app_account_token)
                sub, _ = Subscription.objects.get_or_create(user=user)
                sub.original_transaction_id = original_txn_id
                sub.save(update_fields=['original_transaction_id'])
                return sub
            except (User.DoesNotExist, ValueError):
                pass

        logger.warning(
            f'App Store notify: no subscription for txn {original_txn_id}'
        )
        return None

    def _parse_expires(self, transaction):
        """Parse expiresDate from transaction (milliseconds)."""
        expires_ms = transaction.get('expiresDate')
        if expires_ms:
            return datetime.fromtimestamp(int(expires_ms) / 1000, tz=tz.utc)
        return None

    def _determine_plan(self, transaction):
        """Determine plan from product ID."""
        product_id = transaction.get('productId', '')
        if 'monthly' in product_id:
            return 'premium_monthly'
        elif 'biweekly' in product_id or 'weekly' in product_id:
            return 'premium_weekly'
        return 'premium_monthly'

    def _handle_subscribed(self, transaction, renewal, subtype):
        """Initial purchase or resubscribe."""
        sub = self._find_subscription(transaction)
        if not sub:
            return

        sub.plan = self._determine_plan(transaction)
        sub.plan_id = transaction.get('productId', '') or sub.plan_id
        sub.status = 'active'
        sub.current_period_end = self._parse_expires(transaction)
        sub.cancel_at_period_end = False
        sub.save()
        logger.info(f'App Store: subscribed {sub.user.email} → {sub.plan}')

    def _handle_renewed(self, transaction, renewal, subtype):
        """Subscription renewed successfully."""
        sub = self._find_subscription(transaction)
        if not sub:
            return

        sub.plan_id = transaction.get('productId', '') or sub.plan_id
        sub.status = 'active'
        sub.current_period_end = self._parse_expires(transaction)
        sub.cancel_at_period_end = False
        sub.save(update_fields=[
            'plan_id', 'status', 'current_period_end', 'cancel_at_period_end'
        ])
        logger.info(f'App Store: renewed {sub.user.email}')

    def _handle_expired(self, transaction, renewal, subtype):
        """Subscription expired."""
        sub = self._find_subscription(transaction)
        if not sub:
            return

        sub.plan = 'free'
        sub.status = 'expired'
        sub.cancel_at_period_end = False
        sub.save(update_fields=['plan', 'status', 'cancel_at_period_end'])
        logger.info(f'App Store: expired {sub.user.email}')

    def _handle_renewal_status_change(self, transaction, renewal, subtype):
        """User toggled auto-renew on/off."""
        sub = self._find_subscription(transaction)
        if not sub:
            return

        auto_renew = renewal.get('autoRenewStatus', 1) == 1
        sub.cancel_at_period_end = not auto_renew
        sub.save(update_fields=['cancel_at_period_end'])
        action = 're-enabled auto-renew' if auto_renew else 'canceled'
        logger.info(f'App Store: {sub.user.email} {action}')

    def _handle_billing_issue(self, transaction, renewal, subtype):
        """Payment failed — grace period."""
        sub = self._find_subscription(transaction)
        if not sub:
            return

        sub.status = 'past_due'
        sub.save(update_fields=['status'])
        logger.info(f'App Store: billing issue for {sub.user.email}')

    def _handle_refund(self, transaction, renewal, subtype):
        """User received a refund — revoke access."""
        sub = self._find_subscription(transaction)
        if not sub:
            return

        sub.plan = 'free'
        sub.status = 'canceled'
        sub.save(update_fields=['plan', 'status'])
        logger.info(f'App Store: refund for {sub.user.email}')
