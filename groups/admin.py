from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from .models import (
    AjoGroup,
    GroupMembership,
    GroupMembershipHistory,
)


class GroupMembershipHistoryInline(admin.TabularInline):
    model = GroupMembershipHistory
    extra = 0
    can_delete = False
    fields = (
        "event_type",
        "performed_by",
        "reason",
        "created_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AjoGroup)
class AjoGroupAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "owner",
        "contribution_amount",
        "frequency",
        "max_members",
        "payout_method",
        "status",
        "invitation_active",
        "created_at",
    )

    list_filter = (
        "status",
        "frequency",
        "payout_method",
        "invitation_active",
    )

    search_fields = (
        "name",
        "owner__email",
        "owner__full_name",
    )

    readonly_fields = (
        "invitation_token",
        "created_at",
        "updated_at",
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("owner",)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)

            if not change:
                GroupMembership.objects.get_or_create(
                    group=obj,
                    user=obj.owner,
                    defaults={
                        "role": GroupMembership.Role.OWNER,
                        "status": GroupMembership.Status.APPROVED,
                        "reviewed_by": request.user,
                        "reviewed_at": timezone.now(),
                    }
                )

@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):

    list_display = (
        "group",
        "user",
        "role",
        "status",
        "joined_at",
        "reviewed_by",
        "removed_by",
        "removed_at",
    )

    list_filter = (
        "role",
        "status",
        "joined_at",
    )

    search_fields = (
        "group__name",
        "user__email",
        "user__full_name",
    )

    readonly_fields = tuple(
        field.name for field in GroupMembership._meta.fields
    )

    inlines = [GroupMembershipHistoryInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    
@admin.register(GroupMembershipHistory)
class GroupMembershipHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "membership",
        "event_type",
        "performed_by",
        "created_at",
    )

    list_filter = (
        "event_type",
        "created_at",
    )

    search_fields = (
        "membership__user__email",
        "membership__user__full_name",
        "membership__group__name",
    )

    readonly_fields = (
        "membership",
        "event_type",
        "performed_by",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False