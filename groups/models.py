
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

    rotation_confirmed_at = models.DateTimeField(
        blank=True,
        null=True
    )

    rotation_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="confirmed_ajo_rotations"
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
        null=True,
        validators=[MinValueValidator(1)]
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

class HistoricalImportBatch(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Awaiting member review"
        DISPUTED = "disputed", "Has disputed records"
        READY = "ready", "Ready for activation"
        COMPLETED = "completed", "Completed"

    cycle = models.OneToOneField(
        AjoCycle,
        on_delete=models.CASCADE,
        related_name="historical_import"
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_historical_imports"
    )

    total_completed_rounds = models.PositiveIntegerField(default=0)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Historical import - {self.cycle}"


class AjoRound(models.Model):

    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class RecordSource(models.TextChoices):
        HISTORICAL = "historical", "Imported historical record"
        PLATFORM = "platform", "Managed by Digital Ajo"

    cycle = models.ForeignKey(
        AjoCycle,
        on_delete=models.CASCADE,
        related_name="rounds"
    )

    round_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    participant = models.ForeignKey(
        CycleParticipant,
        on_delete=models.PROTECT,
        related_name="payout_rounds"
    )

    record_source = models.CharField(
        max_length=12,
        choices=RecordSource.choices,
        default=RecordSource.PLATFORM
    )

    scheduled_date = models.DateField(
        blank=True,
        null=True
    )

    payout_date = models.DateField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.UPCOMING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["round_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "round_number"],
                name="unique_round_number_per_cycle"
            )
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.participant_id and self.cycle_id:
            if self.participant.cycle_id != self.cycle_id:
                raise ValidationError({
                    "participant": "The selected participant must belong to this cycle."
                })

    def __str__(self):
        return f"{self.cycle} - Round {self.round_number}"

class HistoricalContribution(models.Model):

    batch = models.ForeignKey(
        HistoricalImportBatch,
        on_delete=models.CASCADE,
        related_name="contributions"
    )

    ajo_round = models.ForeignKey(
        AjoRound,
        on_delete=models.PROTECT,
        related_name="historical_contributions"
    )

    participant = models.ForeignKey(
        CycleParticipant,
        on_delete=models.PROTECT,
        related_name="historical_contributions"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    contribution_date = models.DateField()

    reference = models.CharField(
        max_length=150,
        blank=True
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["contribution_date"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.batch_id and self.ajo_round_id:
            if self.batch.cycle_id != self.ajo_round.cycle_id:
                raise ValidationError(
                    "The round must belong to the import batch's cycle."
                )

        if self.participant_id and self.ajo_round_id:
            if self.participant.cycle_id != self.ajo_round.cycle_id:
                raise ValidationError(
                    "The contributor must belong to the round's cycle."
                )

        if self.ajo_round_id:
            if self.ajo_round.record_source != AjoRound.RecordSource.HISTORICAL:
                raise ValidationError(
                    "Historical contributions must belong to historical rounds."
                )

    def __str__(self):
        return f"{self.participant} - ₦{self.amount}"

class HistoricalPayout(models.Model):

    batch = models.ForeignKey(
        HistoricalImportBatch,
        on_delete=models.CASCADE,
        related_name="payouts"
    )

    ajo_round = models.ForeignKey(
        AjoRound,
        on_delete=models.PROTECT,
        related_name="historical_payouts"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    payout_date = models.DateField()

    reference = models.CharField(
        max_length=150,
        blank=True
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["payout_date"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.batch_id and self.ajo_round_id:
            if self.batch.cycle_id != self.ajo_round.cycle_id:
                raise ValidationError(
                    "The round must belong to the import batch's cycle."
                )

        if self.ajo_round_id:
            if self.ajo_round.record_source != AjoRound.RecordSource.HISTORICAL:
                raise ValidationError(
                    "Historical payouts must belong to historical rounds."
                )

    def __str__(self):
        return f"{self.ajo_round} - ₦{self.amount}"

class HistoricalRecordReview(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting review"
        CONFIRMED = "confirmed", "Confirmed"
        DISPUTED = "disputed", "Disputed"

    batch = models.ForeignKey(
        HistoricalImportBatch,
        on_delete=models.CASCADE,
        related_name="member_reviews"
    )

    participant = models.ForeignKey(
        CycleParticipant,
        on_delete=models.PROTECT,
        related_name="historical_reviews"
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING
    )

    dispute_reason = models.TextField(blank=True)

    resolution_note = models.TextField(blank=True)

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="resolved_historical_reviews"
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["batch", "participant"],
                name="unique_historical_review_per_member"
            )
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.batch_id and self.participant_id:
            if self.batch.cycle_id != self.participant.cycle_id:
                raise ValidationError(
                    "The participant must belong to the import batch's cycle."
                )

    def __str__(self):
        return f"{self.participant} - {self.get_status_display()}"

class HistoricalRecordReviewEvent(models.Model):

    class EventType(models.TextChoices):
        CONFIRMED = "confirmed", "Records confirmed"
        DISPUTED = "disputed", "Records disputed"
        RESOLVED = "resolved", "Dispute resolved"
        REVIEW_REQUESTED = "review_requested", "Review requested again"

    review = models.ForeignKey(
        HistoricalRecordReview,
        on_delete=models.PROTECT,
        related_name="events"
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="historical_review_events"
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.review} - {self.get_event_type_display()}"