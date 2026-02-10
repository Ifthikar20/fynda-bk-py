"""
Deal URLs

URL routing for the deals app.
"""

from django.urls import path
from .views import (
    SearchView, ImageUploadView, HealthView, CsrfView,
    CreateSharedStoryboardView, GetSharedStoryboardView, MySharedStoryboardsView,
    SavedDealsView, SavedDealDetailView,
)

urlpatterns = [
    path('csrf/', CsrfView.as_view(), name='csrf'),
    path('search/', SearchView.as_view(), name='search'),
    path('upload/', ImageUploadView.as_view(), name='upload'),
    path('health/', HealthView.as_view(), name='health'),
    
    # Shared Storyboard endpoints
    path('storyboard/share/', CreateSharedStoryboardView.as_view(), name='create-share'),
    path('storyboard/share/<str:token>/', GetSharedStoryboardView.as_view(), name='get-share'),
    path('storyboard/my-shares/', MySharedStoryboardsView.as_view(), name='my-shares'),
    
    # Saved Deals (web)
    path('saved/', SavedDealsView.as_view(), name='saved-deals'),
    path('saved/<str:deal_id>/', SavedDealDetailView.as_view(), name='saved-deal-detail'),
]
