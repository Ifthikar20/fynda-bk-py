"""
Mobile API URL Configuration

All mobile endpoints are prefixed with /api/mobile/
"""

from django.urls import path
from .views import (
    # Health
    HealthView,
    # Auth
    MobileLoginView,
    MobileRegisterView,
    MobileLogoutView,
    MobileOAuthView,
    # Devices
    DeviceListView,
    DeviceDetailView,
    # Preferences
    PreferencesView,
    # Sync
    SyncView,
    # Deals
    MobileDealListView,
    MobileDealSearchView,
    MobileImageUploadView,
    # Alerts
    PriceAlertListView,
    PriceAlertDetailView,
    # Favorites
    FavoritesView,
    FavoriteDetailView,
    # Storyboard
    MobileStoryboardView,
    MobileStoryboardDetailView,
)

app_name = "mobile"

urlpatterns = [
    # ============================================
    # Health & Status
    # ============================================
    path("health/", HealthView.as_view(), name="health"),
    
    # ============================================
    # Authentication
    # ============================================
    path("auth/login/", MobileLoginView.as_view(), name="login"),
    path("auth/register/", MobileRegisterView.as_view(), name="register"),
    path("auth/logout/", MobileLogoutView.as_view(), name="logout"),
    path("auth/oauth/", MobileOAuthView.as_view(), name="oauth"),
    
    # ============================================
    # Device Management
    # ============================================
    path("devices/", DeviceListView.as_view(), name="device-list"),
    path("devices/<uuid:device_id>/", DeviceDetailView.as_view(), name="device-detail"),
    
    # ============================================
    # User Preferences
    # ============================================
    path("preferences/", PreferencesView.as_view(), name="preferences"),
    
    # ============================================
    # Offline Sync
    # ============================================
    path("sync/", SyncView.as_view(), name="sync"),
    
    # ============================================
    # Deals
    # ============================================
    path("deals/", MobileDealListView.as_view(), name="deal-list"),
    path("deals/search/", MobileDealSearchView.as_view(), name="deal-search"),
    path("deals/image-search/", MobileImageUploadView.as_view(), name="image-search"),
    
    # ============================================
    # Price Alerts
    # ============================================
    path("alerts/", PriceAlertListView.as_view(), name="alert-list"),
    path("alerts/<uuid:alert_id>/", PriceAlertDetailView.as_view(), name="alert-detail"),
    
    # ============================================
    # Favorites / Saved Deals
    # ============================================
    path("favorites/", FavoritesView.as_view(), name="favorites"),
    path("favorites/<str:deal_id>/", FavoriteDetailView.as_view(), name="favorite-detail"),
    
    # ============================================
    # Storyboard
    # ============================================
    path("storyboard/", MobileStoryboardView.as_view(), name="storyboard-list"),
    path("storyboard/<str:token>/", MobileStoryboardDetailView.as_view(), name="storyboard-detail"),
]
