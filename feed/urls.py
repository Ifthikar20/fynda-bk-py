from django.urls import path
from . import views

app_name = "feed"

urlpatterns = [
    path("", views.FeedListCreateView.as_view(), name="feed-list-create"),
    path("me/", views.MyPostsView.as_view(), name="my-posts"),
    path("<uuid:id>/", views.PostDetailView.as_view(), name="post-detail"),
    path("<uuid:id>/like/", views.toggle_like, name="toggle-like"),
    path("<uuid:id>/comments/", views.CommentListCreateView.as_view(), name="comments"),
]
