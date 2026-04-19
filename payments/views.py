"""
Payments API Views

Handles Stripe + Apple Pay subscription management.

Flow:
1. Mobile app calls POST /payments/subscribe/ with plan choice
2. Backend creates Stripe Customer + PaymentIntent + ephemeral key
3. Mobile app presents Apple Pay sheet using client_secret
4. Stripe processes payment, fires webhook
5. Webhook handler activates subscription
"""

import logging
import stripe
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Subscription, Payment
from .serializers import (
    SubscriptionSerializer,
    PaymentSerializer,
    CreatePaymentIntentSerializer,
)

logger = logging.getLogger(__name__)

# Plan pricing in cents (kept for web/Stripe — Apple IAP uses App Store pricing)
PLAN_PRICES = {
    "premium_weekly": {
        "amount": 399,   # $3.99
        "interval_days": 7,
        "label": "Outfi Premium — Weekly",
    },
    "premium_biweekly": {
        "amount": 399,   # $3.99 (legacy alias → weekly)
        "interval_days": 7,
        "label": "Outfi Premium — Weekly",
    },
    "premium_monthly": {
        "amount": 1299,  # $12.99
        "interval_days": 30,
        "label": "Outfi Premium — Monthly",
    },
}


def _get_stripe():
    """Configure and return stripe module."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _get_or_create_customer(user):
    """Get existing Stripe customer or create one."""
    s = _get_stripe()
    sub, _ = Subscription.objects.get_or_create(user=user)

    if sub.stripe_customer_id:
        return sub.stripe_customer_id, sub

    customer = s.Customer.create(
        email=user.email,
        name=f"{user.first_name} {user.last_name}".strip() or user.email,
        metadata={"outfi_user_id": str(user.id)},
    )
    sub.stripe_customer_id = customer.id
    sub.save(update_fields=["stripe_customer_id"])
    return customer.id, sub


class SubscriptionStatusView(APIView):
    """
    GET /payments/status/ — current subscription status + premium features.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = Subscription.objects.filter(user=request.user).first()
        if not sub:
            return Response({
                "plan": "free",
                "plan_id": "",
                "android_package": "",
                "status": "active",
                "is_premium": False,
                "current_period_end": None,
                "expires_at": None,
                "cancel_at_period_end": False,
                "limits": _get_limits(False),
            })

        data = SubscriptionSerializer(sub).data
        data["limits"] = _get_limits(sub.is_premium)
        return Response(data)


class SubscribeView(APIView):
    """
    POST /payments/subscribe/ — create a Stripe PaymentIntent for Apple Pay.

    Request:  { "plan": "premium_monthly", "payment_method": "apple_pay" }
    Response: { "client_secret": "...", "ephemeral_key": "...", "customer_id": "...", ... }

    The mobile app uses client_secret to present the Apple Pay sheet.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreatePaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = serializer.validated_data["plan"]
        payment_method_type = serializer.validated_data["payment_method"]
        plan_info = PLAN_PRICES[plan]

        s = _get_stripe()
        customer_id, sub = _get_or_create_customer(request.user)

        # Already premium? Don't double-charge.
        if sub.is_premium and not sub.cancel_at_period_end:
            return Response(
                {"error": "You already have an active subscription."},
                status=status.HTTP_409_CONFLICT,
            )

        # Map payment method to Stripe payment_method_types
        pm_types = {
            "apple_pay": ["card"],  # Apple Pay uses card token via Stripe
            "google_pay": ["card"],
            "card": ["card"],
        }

        # Create PaymentIntent
        intent = s.PaymentIntent.create(
            amount=plan_info["amount"],
            currency="usd",
            customer=customer_id,
            payment_method_types=pm_types.get(payment_method_type, ["card"]),
            metadata={
                "outfi_user_id": str(request.user.id),
                "plan": plan,
                "payment_method": payment_method_type,
            },
            description=plan_info["label"],
        )

        # Create ephemeral key for mobile SDK
        ephemeral_key = s.EphemeralKey.create(
            customer=customer_id,
            stripe_version="2024-06-20",
        )

        # Record pending payment
        Payment.objects.create(
            user=request.user,
            subscription=sub,
            stripe_payment_intent_id=intent.id,
            amount=plan_info["amount"] / 100,
            currency="USD",
            payment_method=payment_method_type,
            status="pending",
            description=plan_info["label"],
        )

        return Response({
            "client_secret": intent.client_secret,
            "ephemeral_key": ephemeral_key.secret,
            "customer_id": customer_id,
            "payment_intent_id": intent.id,
            "amount": plan_info["amount"],
            "currency": "usd",
            "label": plan_info["label"],
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        })


class CancelSubscriptionView(APIView):
    """
    POST /payments/cancel/ — cancel subscription at period end.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = Subscription.objects.filter(user=request.user).first()
        if not sub or sub.plan == "free":
            return Response(
                {"error": "No active subscription to cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if sub.stripe_subscription_id:
            s = _get_stripe()
            s.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True,
            )

        sub.cancel_at_period_end = True
        sub.save(update_fields=["cancel_at_period_end"])

        return Response({
            "message": "Subscription will cancel at end of billing period.",
            "current_period_end": sub.current_period_end,
        })


class PaymentHistoryView(APIView):
    """
    GET /payments/history/ — list user's payment history.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(
            user=request.user, status="succeeded"
        )[:50]
        return Response({
            "payments": PaymentSerializer(payments, many=True).data,
        })


class RestoreSubscriptionView(APIView):
    """
    POST /payments/restore/ — restore subscription from Apple receipt.

    For users who reinstall or switch devices.
    Checks Stripe customer status to restore premium.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = Subscription.objects.filter(user=request.user).first()
        if not sub or not sub.stripe_customer_id:
            return Response(
                {"error": "No previous subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        s = _get_stripe()
        # Check for active subscriptions on this customer
        stripe_subs = s.Subscription.list(
            customer=sub.stripe_customer_id,
            status="active",
            limit=1,
        )

        if not stripe_subs.data:
            # Also check trialing
            stripe_subs = s.Subscription.list(
                customer=sub.stripe_customer_id,
                status="trialing",
                limit=1,
            )

        if stripe_subs.data:
            stripe_sub = stripe_subs.data[0]
            sub.stripe_subscription_id = stripe_sub.id
            sub.status = stripe_sub.status
            sub.plan = stripe_sub.metadata.get("plan", sub.plan)
            sub.current_period_start = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            )
            sub.current_period_end = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )
            sub.cancel_at_period_end = stripe_sub.cancel_at_period_end
            sub.save()

            return Response({
                "restored": True,
                "subscription": SubscriptionSerializer(sub).data,
            })

        return Response({
            "restored": False,
            "message": "No active subscription found on your account.",
        })


from django.utils.decorators import method_decorator


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    """
    POST /payments/webhook/ — Stripe webhook handler.

    Processes payment events to activate/deactivate subscriptions.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        s = _get_stripe()
        try:
            event = s.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.warning("Stripe webhook: invalid payload")
            return HttpResponse(status=400)
        except s.error.SignatureVerificationError:
            logger.warning("Stripe webhook: invalid signature")
            return HttpResponse(status=400)

        event_type = event["type"]
        data = event["data"]["object"]

        # Idempotency: Stripe may deliver the same event multiple times.
        # Skip if we've already processed this event (24h dedup window).
        from django.core.cache import cache
        event_id = event.get("id", "")
        idempotency_key = f"stripe_event:{event_id}"
        if cache.get(idempotency_key):
            logger.info(f"Stripe webhook: duplicate event {event_id}, skipping")
            return HttpResponse(status=200)
        cache.set(idempotency_key, True, timeout=86400)  # 24 hours

        logger.info(f"Stripe webhook: {event_type}")

        if event_type == "payment_intent.succeeded":
            self._handle_payment_succeeded(data)
        elif event_type == "payment_intent.payment_failed":
            self._handle_payment_failed(data)
        elif event_type == "customer.subscription.updated":
            self._handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            self._handle_subscription_deleted(data)
        elif event_type == "invoice.paid":
            self._handle_invoice_paid(data)

        return HttpResponse(status=200)

    def _handle_payment_succeeded(self, data):
        """Payment succeeded — activate subscription."""
        intent_id = data["id"]
        metadata = data.get("metadata", {})
        plan = metadata.get("plan", "")
        payment_method = metadata.get("payment_method", "card")

        # Update payment record
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=intent_id)
            payment.status = "succeeded"
            payment.receipt_url = data.get("charges", {}).get("data", [{}])[0].get(
                "receipt_url", ""
            ) if data.get("charges") else ""
            payment.save(update_fields=["status", "receipt_url"])

            # Activate subscription
            if plan and payment.subscription:
                sub = payment.subscription
                sub.plan = plan
                sub.status = "active"
                sub.current_period_start = timezone.now()
                days = PLAN_PRICES.get(plan, {}).get("interval_days", 30)
                sub.current_period_end = timezone.now() + timezone.timedelta(days=days)
                sub.cancel_at_period_end = False
                sub.save()
                logger.info(f"Subscription activated: {sub.user.email} → {plan}")
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for intent {intent_id}")

    def _handle_payment_failed(self, data):
        """Payment failed — update record."""
        intent_id = data["id"]
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=intent_id)
            payment.status = "failed"
            payment.save(update_fields=["status"])
        except Payment.DoesNotExist:
            pass

    def _handle_subscription_updated(self, data):
        """Stripe subscription updated — sync status."""
        stripe_sub_id = data["id"]
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            sub.status = data["status"]
            sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
            if data.get("current_period_end"):
                sub.current_period_end = timezone.datetime.fromtimestamp(
                    data["current_period_end"], tz=timezone.utc
                )
            sub.save()
        except Subscription.DoesNotExist:
            pass

    def _handle_subscription_deleted(self, data):
        """Stripe subscription canceled/expired."""
        stripe_sub_id = data["id"]
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            sub.status = "canceled"
            sub.plan = "free"
            sub.save(update_fields=["status", "plan"])
            logger.info(f"Subscription canceled: {sub.user.email}")
        except Subscription.DoesNotExist:
            pass

    def _handle_invoice_paid(self, data):
        """Recurring invoice paid — extend subscription."""
        customer_id = data.get("customer", "")
        try:
            sub = Subscription.objects.get(stripe_customer_id=customer_id)
            sub.status = "active"
            period_end = data.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
            if period_end:
                sub.current_period_end = timezone.datetime.fromtimestamp(
                    period_end, tz=timezone.utc
                )
            sub.save()
        except Subscription.DoesNotExist:
            pass


def _get_limits(is_premium: bool) -> dict:
    """Return feature limits based on subscription tier."""
    if is_premium:
        return {
            "daily_image_searches": 25,
            "biweekly_image_searches": 250,
            "daily_price_alerts": 100,
            "saved_deals_max": 1000,
            "storyboards_max": 50,
            "ad_free": True,
        }
    return {
        "daily_image_searches": 3,
        "biweekly_image_searches": 20,
        "daily_price_alerts": 10,
        "saved_deals_max": 50,
        "storyboards_max": 5,
        "ad_free": False,
    }
