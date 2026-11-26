from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    AjoCycle,
    AjoRound,
    CycleParticipant,
    GroupMembership,
    HistoricalContribution,
    HistoricalImportBatch,
)


@transaction.atomic
def create_historical_import_batch(
    *,
    cycle_id,
    actor,
    total_completed_rounds,
    notes="",
):
    """
    Create a historical import batch for an existing Ajo cycle.

    Only the group owner can create the batch.
    The cycle must still be in its setup stage.
    """

    if not actor or not actor.is_authenticated:
        raise ValidationError("Authentication is required.")

    # Lock the cycle while validating and creating the batch.
    cycle = (
        AjoCycle.objects
        .select_for_update()
        .select_related("group")
        .get(pk=cycle_id)
    )

    # Only the group owner can import historical records.
    if cycle.group.owner_id != actor.pk:
        raise ValidationError(
            "Only the group owner can create a historical import."
        )

    # Historical imports are only for existing Ajo arrangements.
    if cycle.onboarding_type != AjoCycle.OnboardingType.EXISTING:
        raise ValidationError(
            "Historical imports are only available for existing Ajo arrangements."
        )

    # Do not allow historical setup after the cycle has started.
    if cycle.status not in [
        AjoCycle.Status.DRAFT,
        AjoCycle.Status.SETUP,
    ]:
        raise ValidationError(
            "Historical records cannot be imported after the cycle starts."
        )

    # Prevent duplicate imports.
    if HistoricalImportBatch.objects.filter(cycle=cycle).exists():
        raise ValidationError(
            "A historical import batch already exists for this cycle."
        )

    if not isinstance(total_completed_rounds, int) or isinstance(
        total_completed_rounds, bool
    ):
        raise ValidationError(
            "Completed rounds must be a whole number."
        )

    if total_completed_rounds < 0:
        raise ValidationError(
            "Completed rounds cannot be negative."
        )

    active_participants = CycleParticipant.objects.filter(
        cycle=cycle,
        status=CycleParticipant.Status.ACTIVE,
    )

    participant_count = active_participants.count()

    if participant_count < 2:
        raise ValidationError(
            "At least two active participants are required."
        )

    # Every active participant must have an approved group membership.
    approved_count = active_participants.filter(
        membership__status=GroupMembership.Status.APPROVED,
    ).count()

    if approved_count != participant_count:
        raise ValidationError(
            "All cycle participants must have approved group memberships."
        )

    # An ongoing rotation must have at least one payout round remaining.
    if total_completed_rounds >= participant_count:
        raise ValidationError(
            "Completed rounds must be fewer than the total participants."
        )

    batch = HistoricalImportBatch(
        cycle=cycle,
        created_by=actor,
        total_completed_rounds=total_completed_rounds,
        notes=notes.strip(),
    )

    batch.full_clean()
    batch.save()

    return batch

@transaction.atomic
def create_historical_rounds(
    *,
    batch_id,
    actor,
):
    """
    Create completed historical rounds using the original payout order.

    The participant with payout_position=1 receives historical round 1,
    position=2 receives historical round 2, and so on.
    """

    if not actor or not actor.is_authenticated:
        raise ValidationError("Authentication is required.")

    batch = (
        HistoricalImportBatch.objects
        .select_for_update()
        .select_related("cycle__group")
        .get(pk=batch_id)
    )

    cycle = batch.cycle

    if cycle.group.owner_id != actor.pk:
        raise ValidationError(
            "Only the group owner can create historical rounds."
        )

    if cycle.onboarding_type != AjoCycle.OnboardingType.EXISTING:
        raise ValidationError(
            "Historical rounds are only available for existing Ajo arrangements."
        )

    if cycle.status not in [
        AjoCycle.Status.DRAFT,
        AjoCycle.Status.SETUP,
    ]:
        raise ValidationError(
            "Historical rounds cannot be created after the cycle starts."
        )

    if batch.status != HistoricalImportBatch.Status.DRAFT:
        raise ValidationError(
            "Historical rounds can only be created while the import is in draft."
        )

    if AjoRound.objects.filter(cycle=cycle).exists():
        raise ValidationError(
            "Rounds already exist for this cycle. Historical rounds cannot be duplicated."
        )

    participants = list(
        CycleParticipant.objects
        .select_for_update()
        .select_related("membership")
        .filter(
            cycle=cycle,
            status=CycleParticipant.Status.ACTIVE,
        )
        .order_by("payout_position")
    )

    participant_count = len(participants)

    if participant_count < 2:
        raise ValidationError(
            "At least two active participants are required."
        )

    if any(
        participant.membership.status != GroupMembership.Status.APPROVED
        for participant in participants
    ):
        raise ValidationError(
            "All active participants must have approved memberships."
        )

    positions = [
        participant.payout_position
        for participant in participants
    ]

    expected_positions = list(range(1, participant_count + 1))

    if positions != expected_positions:
        raise ValidationError(
            "The payout order must be complete and consecutive before historical rounds can be created."
        )

    if batch.total_completed_rounds >= participant_count:
        raise ValidationError(
            "Completed rounds must be fewer than the total participants."
        )

    created_rounds = []

    for round_number in range(1, batch.total_completed_rounds + 1):
        recipient = next(
            participant
            for participant in participants
            if participant.payout_position == round_number
        )

        ajo_round = AjoRound(
            cycle=cycle,
            round_number=round_number,
            participant=recipient,
            record_source=AjoRound.RecordSource.HISTORICAL,
            status=AjoRound.Status.COMPLETED,
        )

        ajo_round.full_clean()
        ajo_round.save()

        created_rounds.append(ajo_round)

    return created_rounds


@transaction.atomic
def create_historical_contribution(
    *,
    batch_id,
    round_id,
    participant_id,
    actor,
    amount,
    contribution_date,
    reference="",
    notes="",
):
    """
    Record a participant's actual contribution to a completed
    historical round.

    Multiple contributions by the same participant in the same
    round are allowed to support partial payments.
    """

    if not actor or not actor.is_authenticated:
        raise ValidationError("Authentication is required.")

    # Lock the batch to protect the import operation.
    batch = (
        HistoricalImportBatch.objects
        .select_for_update()
        .select_related("cycle__group")
        .get(pk=batch_id)
    )

    cycle = batch.cycle

    if cycle.group.owner_id != actor.pk:
        raise ValidationError(
            "Only the group owner can record historical contributions."
        )

    if cycle.onboarding_type != AjoCycle.OnboardingType.EXISTING:
        raise ValidationError(
            "Historical contributions are only available for existing Ajo arrangements."
        )

    if cycle.status not in [
        AjoCycle.Status.DRAFT,
        AjoCycle.Status.SETUP,
    ]:
        raise ValidationError(
            "Historical contributions cannot be recorded after the cycle starts."
        )

    if batch.status != HistoricalImportBatch.Status.DRAFT:
        raise ValidationError(
            "Historical contributions can only be recorded while the import is in draft."
        )

    # The round must belong to this cycle.
    ajo_round = (
        AjoRound.objects
        .select_for_update()
        .filter(
            pk=round_id,
            cycle=cycle,
        )
        .first()
    )

    if not ajo_round:
        raise ValidationError(
            "The selected round does not belong to this historical import."
        )

    if ajo_round.record_source != AjoRound.RecordSource.HISTORICAL:
        raise ValidationError(
            "Contributions can only be recorded against historical rounds."
        )

    if ajo_round.status != AjoRound.Status.COMPLETED:
        raise ValidationError(
            "Contributions can only be recorded against completed historical rounds."
        )

    # The participant must belong to the same cycle.
    participant = (
        CycleParticipant.objects
        .select_for_update()
        .filter(
            pk=participant_id,
            cycle=cycle,
        )
        .first()
    )

    if not participant:
        raise ValidationError(
            "The selected participant does not belong to this Ajo cycle."
        )

    contribution = HistoricalContribution(
        batch=batch,
        ajo_round=ajo_round,
        participant=participant,
        amount=amount,
        contribution_date=contribution_date,
        reference=reference.strip(),
        notes=notes.strip(),
    )

    # Runs field validation and the model's clean() checks.
    contribution.full_clean()
    contribution.save()

    return contribution
