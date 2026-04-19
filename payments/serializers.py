"""
Payments API Serializers
"""

from rest_framework import serializers
from .models import Subscription, Payment


class SubscriptionSerializer(serializers.ModelSerializer):
    is_premium = serializers.BooleanField(read_only=True)
    # Alias — mobile's Manage Subscription screen falls back to `expires_at`
    # when `current_period_end` is absent. Keep both populated.
    expires_at = serializers.DateTimeField(source="current_period_end", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "plan_id",
            "android_package",
            "status",
            "is_premium",
            "current_period_start",
            "current_period_end",
            "expires_at",
            "cancel_at_period_end",
            "trial_end",
            "created_at",
        ]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "currency",
            "payment_method",
            "status",
            "description",
            "receipt_url",
            "created_at",
        ]
        read_only_fields = fields


class CreatePaymentIntentSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["premium_biweekly", "premium_monthly"])
    payment_method = serializers.ChoiceField(
        choices=["apple_pay", "google_pay", "card"],
        default="apple_pay",
    )
