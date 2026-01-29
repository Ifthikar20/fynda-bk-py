"""
Deal URLs

URL routing for the deals app.
"""

from django.urls import path
from .views import SearchView, ImageUploadView, HealthView

urlpatterns = [
    path('search/', SearchView.as_view(), name='search'),
    path('upload/', ImageUploadView.as_view(), name='upload'),
    path('health/', HealthView.as_view(), name='health'),
]
