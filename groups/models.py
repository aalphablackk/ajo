
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