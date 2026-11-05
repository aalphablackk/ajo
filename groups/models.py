
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
import uuid

class AjoGroup(models.Model):

    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Every two weeks"
        MONTHLY = "monthly", "Monthly"

    class PayoutMethod(models.TextChoices):
        MANUAL = "manual", "Manual"
        RANDOM = "random", "Random"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open for members"
        CLOSED = "closed", "Closed to new members"
        READY = "ready", "Ready to start"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_ajo_groups"
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    contribution_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.MONTHLY
    )

    max_members = models.PositiveIntegerField(
        validators=[MinValueValidator(2)]
    )

    start_date = models.DateField(
        blank=True,
        null=True
    )

    payout_method = models.CharField(
        max_length=10,
        choices=PayoutMethod.choices,
        default=PayoutMethod.MANUAL
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT
    )
    invitation_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    invitation_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REMOVED = "removed", "Removed"

    group = models.ForeignKey(
        AjoGroup,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ajo_memberships"
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_memberships"
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True
    )
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="removed_ajo_memberships"
    )

    removed_at = models.DateTimeField(
        blank=True,
        null=True
    )

    removal_reason = models.CharField(
        max_length=255,
        blank=True
    )

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_user_per_ajo_group"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.group}"

class GroupMembershipHistory(models.Model):

    class EventType(models.TextChoices):
        REMOVED = "removed", "Removed"
        REJOINED = "rejoined", "Rejoined"

    membership = models.ForeignKey(
        GroupMembership,
        on_delete=models.CASCADE,
        related_name="history"
    )

    event_type = models.CharField(
        max_length=10,
        choices=EventType.choices
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="ajo_membership_events"
    )

    reason = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.membership.user} - {self.get_event_type_display()}"


class AjoCycle(models.Model):

    class OnboardingType(models.TextChoices):
        NEW = "new", "New Ajo"
        EXISTING = "existing", "Existing Ajo"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SETUP = "setup", "Setting up"
        READY = "ready", "Ready to start"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    group = models.ForeignKey(
        AjoGroup,
        on_delete=models.CASCADE,
        related_name="cycles"
    )

    cycle_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    onboarding_type = models.CharField(
        max_length=10,
        choices=OnboardingType.choices,
        default=OnboardingType.NEW
    )

    contribution_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    frequency = models.CharField(
        max_length=10,
        choices=AjoGroup.Frequency.choices,
        default=AjoGroup.Frequency.MONTHLY
    )

    payout_method = models.CharField(
        max_length=10,
        choices=AjoGroup.PayoutMethod.choices,
        default=AjoGroup.PayoutMethod.MANUAL
    )

    start_date = models.DateField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group", "cycle_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "cycle_number"],
                name="unique_cycle_number_per_group"
            )
        ]

    def __str__(self):
        return f"{self.group.name} - Cycle {self.cycle_number}"


class CycleParticipant(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"

    cycle = models.ForeignKey(
        AjoCycle,
        on_delete=models.CASCADE,
        related_name="participants"
    )

    membership = models.ForeignKey(
        GroupMembership,
        on_delete=models.PROTECT,
        related_name="cycle_participations"
    )

    payout_position = models.PositiveIntegerField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["payout_position", "joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "membership"],
                name="unique_membership_per_cycle"
            ),
            models.UniqueConstraint(
                fields=["cycle", "payout_position"],
                name="unique_payout_position_per_cycle"
            ),
        ]

    def __str__(self):
        return f"{self.membership.user} - {self.cycle}"
