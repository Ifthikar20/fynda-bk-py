"""
RevenueCat Webhook Handler

Receives webhook events from RevenueCat when Apple IAP subscription
events occur (purchase, renewal, cancellation, expiration, etc.).

Security:
  - Verifies the Authorization header against REVENUECAT_WEBHOOK_SECRET
  - CSRF exempt (external API callback)
  - Returns 200 quickly, defers heavy work

RevenueCat Event Types:
  - INITIAL_PURCHASE    → User subscribed for the first time
  - RENEWAL             → Subscription renewed successfully
  - CANCELLATION        → User canceled (will expire at period end)
  - UNCANCELLATION      → User re-enabled auto-renew
  - EXPIRATION          → Subscription expired
  - BILLING_ISSUE       → Payment failed (grace period)
  - PRODUCT_CHANGE      → User changed plan (upgrade/downgrade)
  - SUBSCRIBER_ALIAS    → RevenueCat linked user IDs
"""

import json
import logging
from datetime import datetime, timezone as tz

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .models import Subscription

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class RevenueCatWebhookView(APIView):
    """
    POST /payments/revenuecat-webhook/ — RevenueCat webhook handler.

    Verifies Authorization header, then processes the event to
    activate/deactivate subscriptions in our database.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # ── Verify Authorization header ──────────────────────
        webhook_secret = getattr(settings, 'REVENUECAT_WEBHOOK_SECRET', '')
        if not webhook_secret:
            logger.error('RevenueCat webhook: REVENUECAT_WEBHOOK_SECRET not configured')
            return HttpResponse(status=500)

        auth_header = request.headers.get('Authorization', '')
        if auth_header != webhook_secret:
            logger.warning('RevenueCat webhook: invalid authorization header')
            return HttpResponse(status=403)

        # ── Parse payload ────────────────────────────────────
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            logger.warning('RevenueCat webhook: invalid JSON payload')
            return HttpResponse(status=400)

        event = payload.get('event', {})
        event_type = event.get('type', '')
        app_user_id = event.get('app_user_id', '')

        logger.info(f'RevenueCat webhook: {event_type} for user {app_user_id}')

        if not app_user_id:
            logger.warning('RevenueCat webhook: missing app_user_id')
            return HttpResponse(status=200)  # Don't retry

        # ── Route to handler ─────────────────────────────────
        handler_map = {
            'INITIAL_PURCHASE': self._handle_purchase,
            'RENEWAL': self._handle_renewal,
            'CANCELLATION': self._handle_cancellation,
            'UNCANCELLATION': self._handle_uncancellation,
            'EXPIRATION': self._handle_expiration,
            'BILLING_ISSUE': self._handle_billing_issue,
            'PRODUCT_CHANGE': self._handle_purchase,  # Treat like new purchase
        }

        handler = handler_map.get(event_type)
        if handler:
            try:
                handler(event, app_user_id)
            except Exception as e:
                logger.error(f'RevenueCat webhook: handler error: {e}', exc_info=True)
                # Return 200 to prevent retries on our bugs
        else:
            logger.info(f'RevenueCat webhook: unhandled event type: {event_type}')

        return HttpResponse(status=200)

    def _get_or_create_subscription(self, app_user_id):
        """Get subscription by RevenueCat app_user_id or Django user ID."""
        # Try RevenueCat user ID first
        sub = Subscription.objects.filter(
            revenuecat_app_user_id=app_user_id
        ).first()

        if sub:
            return sub

        # Try matching by Django user ID (RevenueCat uses our user ID)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=app_user_id)
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.revenuecat_app_user_id = app_user_id
            sub.save(update_fields=['revenuecat_app_user_id'])
            return sub
        except (User.DoesNotExist, ValueError):
            pass

        # Try matching by email (RevenueCat may use email as alias)
        try:
            user = User.objects.get(email=app_user_id)
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.revenuecat_app_user_id = app_user_id
            sub.save(update_fields=['revenuecat_app_user_id'])
            return sub
        except User.DoesNotExist:
            pass

        logger.warning(f'RevenueCat: no user found for app_user_id={app_user_id}')
        return None

    def _parse_iso_date(self, date_str):
        """Parse ISO 8601 date string to datetime."""
        if not date_str:
            return None
        try:
            # Handle various ISO formats
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None

    def _determine_plan(self, event):
        """Determine plan from product ID."""
        product_id = event.get('product_id', '')
        if 'monthly' in product_id:
            return 'premium_monthly'
        elif 'biweekly' in product_id or 'two_week' in product_id:
            return 'premium_biweekly'
        return 'premium_monthly'  # Default

    def _handle_purchase(self, event, app_user_id):
        """Initial purchase or product change — activate subscription."""
        sub = self._get_or_create_subscription(app_user_id)
        if not sub:
            return

        plan = self._determine_plan(event)
        expiration = self._parse_iso_date(event.get('expiration_at_ms') or event.get('expiration_at'))

        # Store Apple transaction ID for receipt tracking
        original_txn_id = event.get('original_transaction_id', '')

        sub.plan = plan
        sub.status = 'active'
        sub.current_period_start = datetime.now(tz.utc)
        sub.current_period_end = expiration
        sub.cancel_at_period_end = False
        if original_txn_id:
            sub.original_transaction_id = original_txn_id
        sub.save()

        logger.info(f'RevenueCat: activated {plan} for user {sub.user.email}')

    def _handle_renewal(self, event, app_user_id):
        """Subscription renewed — extend period."""
        sub = self._get_or_create_subscription(app_user_id)
        if not sub:
            return

        expiration = self._parse_iso_date(event.get('expiration_at_ms') or event.get('expiration_at'))

        sub.status = 'active'
        sub.current_period_end = expiration
        sub.cancel_at_period_end = False
        sub.save(update_fields=['status', 'current_period_end', 'cancel_at_period_end'])

        logger.info(f'RevenueCat: renewed subscription for {sub.user.email}')

    def _handle_cancellation(self, event, app_user_id):
        """User canceled — will expire at period end."""
        sub = self._get_or_create_subscription(app_user_id)
        if not sub:
            return

        sub.cancel_at_period_end = True
        sub.save(update_fields=['cancel_at_period_end'])

        logger.info(f'RevenueCat: user {sub.user.email} canceled (expires at period end)')

    def _handle_uncancellation(self, event, app_user_id):
        """User re-enabled auto-renew."""
        sub = self._get_or_create_subscription(app_user_id)
        if not sub:
            return

        sub.cancel_at_period_end = False
        sub.save(update_fields=['cancel_at_period_end'])

        logger.info(f'RevenueCat: user {sub.user.email} re-enabled auto-renew')

    def _handle_expiration(self, event, app_user_id):
        """Subscription expired — downgrade to free."""
        sub = self._get_or_create_subscription(app_user_id)
        if not sub:
            return

        sub.plan = 'free'
        sub.status = 'expired'
        sub.cancel_at_period_end = False
        sub.save(update_fields=['plan', 'status', 'cancel_at_period_end'])

        logger.info(f'RevenueCat: subscription expired for {sub.user.email}')

    def _handle_billing_issue(self, event, app_user_id):
        """Billing issue — mark as past due (grace period)."""
        sub = self._get_or_create_subscription(app_user_id)
        if not sub:
            return

        sub.status = 'past_due'
        sub.save(update_fields=['status'])

        logger.info(f'RevenueCat: billing issue for {sub.user.email}')
