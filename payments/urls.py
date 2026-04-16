"""
Payments URL Configuration
"""

from django.urls import path
from .views import (
    SubscriptionStatusView,
    SubscribeView,
    CancelSubscriptionView,
    PaymentHistoryView,
    RestoreSubscriptionView,
    StripeWebhookView,
)
from .views_appstore import (
    VerifyIOSReceiptView,
    AppStoreNotificationView,
)

app_name = "payments"

urlpatterns = [
    # Subscription status & history
    path("status/", SubscriptionStatusView.as_view(), name="status"),
    path("history/", PaymentHistoryView.as_view(), name="history"),
    path("cancel/", CancelSubscriptionView.as_view(), name="cancel"),
    path("restore/", RestoreSubscriptionView.as_view(), name="restore"),

    # Apple IAP (native StoreKit)
    path("verify-ios/", VerifyIOSReceiptView.as_view(), name="verify-ios"),
    path("appstore-notify/", AppStoreNotificationView.as_view(), name="appstore-notify"),

    # Stripe (web-only, kept for future web subscriptions)
    path("subscribe/", SubscribeView.as_view(), name="subscribe"),
    path("webhook/", StripeWebhookView.as_view(), name="webhook"),
]
