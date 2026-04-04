from django.contrib import admin
from .models import Subscription, Payment


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "is_premium", "current_period_end", "created_at"]
    list_filter = ["plan", "status"]
    search_fields = ["user__email", "stripe_customer_id"]
    readonly_fields = ["id", "stripe_customer_id", "stripe_subscription_id", "created_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["user", "amount", "currency", "payment_method", "status", "created_at"]
    list_filter = ["status", "payment_method"]
    search_fields = ["user__email", "stripe_payment_intent_id"]
    readonly_fields = ["id", "stripe_payment_intent_id", "created_at"]
