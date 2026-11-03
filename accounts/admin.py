
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserCreationForm, UserChangeForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    form = UserChangeForm
    add_form = UserCreationForm

    list_display = (
        "email",
        "full_name",
        "phone_number",
        "email_verified",
        "phone_verified",
        "is_active",
        "is_staff",
        "date_joined",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "email_verified",
        "phone_verified",
    )

    search_fields = ("email", "full_name", "phone_number")
    ordering = ("-date_joined",)

    readonly_fields = (
        "last_login",
        "date_joined",
        "updated_at",
    )

    fieldsets = (
        ("Account Information", {
            "fields": (
                "email",
                "full_name",
                "phone_number",
                "profile_picture",
            )
        }),
        ("Verification", {
            "fields": (
                "email_verified",
                "phone_verified",
            )
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Important Dates", {
            "fields": (
                "last_login",
                "date_joined",
                "updated_at",
            )
        }),
    )

    add_fieldsets = (
        ("Create Account", {
            "classes": ("wide",),
            "fields": (
                "email",
                "full_name",
                "phone_number",
                "password1",
                "password2",
                "is_active",
                "is_staff",
            ),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")
