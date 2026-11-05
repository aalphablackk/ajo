from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from .models import (
    AjoGroup,
    GroupMembership,
    GroupMembershipHistory,
    AjoCycle,
    CycleParticipant,
)


# --------------------------------------------------
# GROUP MEMBERSHIP HISTORY
# --------------------------------------------------

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


# --------------------------------------------------
# CYCLE PARTICIPANTS INLINE
# --------------------------------------------------

class CycleParticipantInline(admin.TabularInline):
    model = CycleParticipant
    extra = 0
    can_delete = False

    fields = (
        "membership",
        "status",
        "payout_position",
        "joined_at",
    )

    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


# --------------------------------------------------
# AJO GROUP
# --------------------------------------------------

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
        readonly = list(self.readonly_fields)

        if obj:
            readonly.append("owner")

            cycle_has_started = obj.cycles.filter(
                status__in=[
                    AjoCycle.Status.ACTIVE,
                    AjoCycle.Status.COMPLETED,
                ]
            ).exists()

            group_is_locked = obj.status in [
                AjoGroup.Status.ACTIVE,
                AjoGroup.Status.COMPLETED,
                AjoGroup.Status.CANCELLED,
            ]

            if cycle_has_started or group_is_locked:
                readonly.extend([
                    "name",
                    "description",
                    "contribution_amount",
                    "frequency",
                    "max_members",
                    "start_date",
                    "payout_method",
                    "status",
                ])

        return readonly

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)

            if not change:
                membership, _ = GroupMembership.objects.get_or_create(
                    group=obj,
                    user=obj.owner,
                    defaults={
                        "role": GroupMembership.Role.OWNER,
                        "status": GroupMembership.Status.APPROVED,
                        "reviewed_by": request.user,
                        "reviewed_at": timezone.now(),
                    },
                )

                cycle, _ = AjoCycle.objects.get_or_create(
                    group=obj,
                    cycle_number=1,
                    defaults={
                        "onboarding_type": AjoCycle.OnboardingType.NEW,
                        "contribution_amount": obj.contribution_amount,
                        "frequency": obj.frequency,
                        "payout_method": obj.payout_method,
                        "start_date": obj.start_date,
                        "status": AjoCycle.Status.DRAFT,
                    },
                )

                CycleParticipant.objects.get_or_create(
                    cycle=cycle,
                    membership=membership,
                    defaults={
                        "status": CycleParticipant.Status.ACTIVE,
                    },
                )


# --------------------------------------------------
# GROUP MEMBERSHIP
# --------------------------------------------------

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


# --------------------------------------------------
# GROUP MEMBERSHIP HISTORY
# --------------------------------------------------

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


# --------------------------------------------------
# AJO CYCLE
# --------------------------------------------------

@admin.register(AjoCycle)
class AjoCycleAdmin(admin.ModelAdmin):

    list_display = (
        "group",
        "cycle_number",
        "onboarding_type",
        "contribution_amount",
        "frequency",
        "payout_method",
        "status",
        "start_date",
        "created_at",
    )

    list_filter = (
        "status",
        "onboarding_type",
        "frequency",
        "payout_method",
    )

    search_fields = (
        "group__name",
        "group__owner__email",
    )

    readonly_fields = tuple(
        field.name for field in AjoCycle._meta.fields
    )

    inlines = [CycleParticipantInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


# --------------------------------------------------
# CYCLE PARTICIPANTS
# --------------------------------------------------

@admin.register(CycleParticipant)
class CycleParticipantAdmin(admin.ModelAdmin):

    list_display = (
        "cycle",
        "membership",
        "status",
        "payout_position",
        "joined_at",
    )

    list_filter = (
        "status",
        "cycle__status",
        "cycle__group",
    )

    search_fields = (
        "membership__user__email",
        "membership__user__full_name",
        "cycle__group__name",
    )

    readonly_fields = tuple(
        field.name for field in CycleParticipant._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True