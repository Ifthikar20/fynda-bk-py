"""
Payments & Subscriptions Models

Handles Outfi Premium subscriptions via Stripe + Apple Pay.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Subscription(models.Model):
    """
    User subscription for Outfi Premium.

    Managed via Stripe — supports Apple Pay, Google Pay, and card payments.
    """

    PLAN_CHOICES = [
        ("free", "Free"),
        ("premium_biweekly", "Premium — 2 Weeks"),
        ("premium_monthly", "Premium — Monthly"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("expired", "Expired"),
        ("trialing", "Trialing"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )

    # Stripe references
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")

    # Plan
    plan = models.CharField(max_length=30, choices=PLAN_CHOICES, default="free")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Billing cycle
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Trial
    trial_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments_subscriptions"
        indexes = [
            models.Index(fields=["stripe_customer_id"]),
            models.Index(fields=["stripe_subscription_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.plan} ({self.status})"

    @property
    def is_premium(self) -> bool:
        if self.plan == "free":
            return False
        if self.status in ("active", "trialing"):
            return True
        if self.status == "past_due" and self.current_period_end:
            return self.current_period_end > timezone.now()
        return False


class Payment(models.Model):
    """
    Individual payment record.

    Tracks every successful charge for receipts and history.
    """

    PAYMENT_METHOD_CHOICES = [
        ("apple_pay", "Apple Pay"),
        ("google_pay", "Google Pay"),
        ("card", "Card"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    # Stripe reference
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)

    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Payment details
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="card"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    description = models.CharField(max_length=255, blank=True, default="")

    # Receipt
    receipt_url = models.URLField(max_length=1000, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments_payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["stripe_payment_intent_id"]),
        ]

    def __str__(self):
        return f"${self.amount} {self.currency} — {self.status} ({self.payment_method})"
