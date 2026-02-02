"""
URL routes for Email app
"""

from django.urls import path
from . import views

urlpatterns = [
    # Subscription endpoints
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/<str:token>/', views.unsubscribe, name='unsubscribe'),
    
    # Tracking endpoints
    path('email/track/open/<str:tracking_id>/', views.track_open, name='track_open'),
    path('email/track/click/<str:tracking_id>/', views.track_click, name='track_click'),
    
    # Stats
    path('subscribers/count/', views.subscriber_count, name='subscriber_count'),
]
