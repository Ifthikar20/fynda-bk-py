"""
Deal URLs

URL routing for the deals app.
"""

from django.urls import path
from .views import (
    SearchView, InstantSearchView, ImageUploadView, HealthView, CsrfView,
    CreateSharedStoryboardView, GetSharedStoryboardView, MySharedStoryboardsView,
    SavedDealsView, SavedDealDetailView,
    FeaturedContentView,
    ExploreView, VendorStatusView,
)
from .views.brand_views import BrandListView, BrandLikeView
from .views.chat_view import ChatView
from .views.pinterest_views import (
    PinterestStatusView,
    PinterestAuthView,
    PinterestCallbackView,
    PinterestBoardsView,
    PinterestPublishView,
    PinterestDisconnectView,
)
from mobile.remove_bg_view import RemoveBackgroundView
from .views.price_views import PriceAnalysisView

urlpatterns = [
    path('csrf/', CsrfView.as_view(), name='csrf'),
    path('search/instant/', InstantSearchView.as_view(), name='instant-search'),
    path('search/', SearchView.as_view(), name='search'),
    path('upload/', ImageUploadView.as_view(), name='upload'),
    path('health/', HealthView.as_view(), name='health'),
    path('featured/', FeaturedContentView.as_view(), name='featured'),
    path('explore/', ExploreView.as_view(), name='explore'),
    path('vendors/status/', VendorStatusView.as_view(), name='vendor-status'),
    path('chat/', ChatView.as_view(), name='chat'),
    
    # Shared Storyboard endpoints
    path('storyboard/share/', CreateSharedStoryboardView.as_view(), name='create-share'),
    path('storyboard/share/<str:token>/', GetSharedStoryboardView.as_view(), name='get-share'),
    path('storyboard/my-shares/', MySharedStoryboardsView.as_view(), name='my-shares'),
    
    # Saved Deals (web)
    path('saved/', SavedDealsView.as_view(), name='saved-deals'),
    path('saved/<str:deal_id>/', SavedDealDetailView.as_view(), name='saved-deal-detail'),
    
    # Brands
    path('brands/', BrandListView.as_view(), name='brand-list'),
    path('brands/<slug:slug>/like/', BrandLikeView.as_view(), name='brand-like'),
    
    # Pinterest Auto-Publish
    path('pinterest/status/', PinterestStatusView.as_view(), name='pinterest-status'),
    path('pinterest/auth/', PinterestAuthView.as_view(), name='pinterest-auth'),
    path('pinterest/callback/', PinterestCallbackView.as_view(), name='pinterest-callback'),
    path('pinterest/boards/', PinterestBoardsView.as_view(), name='pinterest-boards'),
    path('pinterest/publish/', PinterestPublishView.as_view(), name='pinterest-publish'),
    path('pinterest/disconnect/', PinterestDisconnectView.as_view(), name='pinterest-disconnect'),
    
    # Tools (web-accessible — not behind mobile prefix)
    path('tools/remove-bg/', RemoveBackgroundView.as_view(), name='remove-bg'),
    
    # Price Analysis
    path('price-analysis/', PriceAnalysisView.as_view(), name='price-analysis'),
]
