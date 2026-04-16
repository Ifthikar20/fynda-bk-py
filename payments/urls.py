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
from .views_revenuecat import RevenueCatWebhookView

app_name = "payments"

urlpatterns = [
    path("status/", SubscriptionStatusView.as_view(), name="status"),
    path("subscribe/", SubscribeView.as_view(), name="subscribe"),
    path("cancel/", CancelSubscriptionView.as_view(), name="cancel"),
    path("history/", PaymentHistoryView.as_view(), name="history"),
    path("restore/", RestoreSubscriptionView.as_view(), name="restore"),
    path("webhook/", StripeWebhookView.as_view(), name="webhook"),
    path("revenuecat-webhook/", RevenueCatWebhookView.as_view(), name="revenuecat-webhook"),
]
