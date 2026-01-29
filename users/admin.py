from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "last_name", "is_active", "created_at"]
    search_fields = ["email", "first_name", "last_name"]
    list_filter = ["is_active", "is_staff"]
    ordering = ["-created_at"]
