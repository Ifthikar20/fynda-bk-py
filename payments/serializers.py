"""
Payments API Serializers
"""

from rest_framework import serializers
from .models import Subscription, Payment


class SubscriptionSerializer(serializers.ModelSerializer):
    is_premium = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "is_premium",
            "current_period_start",
            "current_period_end",
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
