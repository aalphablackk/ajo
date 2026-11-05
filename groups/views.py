from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import AjoGroupForm
from .models import AjoGroup, GroupMembership, GroupMembershipHistory,AjoCycle,CycleParticipant
from django.db.models import Count, Q



@login_required
def create_group(request):

    if request.method == "POST":
        form = AjoGroupForm(request.POST)

        if form.is_valid():
            with transaction.atomic():

                # Create the group.
                group = form.save(commit=False)
                group.owner = request.user
                group.save()

                # Add the owner as an approved group member.
                owner_membership = GroupMembership.objects.create(
                    group=group,
                    user=request.user,
                    role=GroupMembership.Role.OWNER,
                    status=GroupMembership.Status.APPROVED,
                    reviewed_by=request.user,
                    reviewed_at=timezone.now(),
                )

                # Automatically create the first Ajo cycle.
                cycle = AjoCycle.objects.create(
                    group=group,
                    cycle_number=1,
                    onboarding_type=AjoCycle.OnboardingType.NEW,
                    contribution_amount=group.contribution_amount,
                    frequency=group.frequency,
                    payout_method=group.payout_method,
                    start_date=group.start_date,
                    status=AjoCycle.Status.DRAFT,
                )

                # Add the owner as the first cycle participant.
                CycleParticipant.objects.create(
                    cycle=cycle,
                    membership=owner_membership,
                    status=CycleParticipant.Status.ACTIVE,
                )

            messages.success(
                request,
                "Your Ajo group and first cycle have been created successfully."
            )

            return redirect("groups:my_groups")

    else:
        form = AjoGroupForm()

    return render(
        request,
        "groups/create_group.html",
        {"form": form}
    )

@login_required
def my_groups(request):

    memberships = (
        GroupMembership.objects
        .filter(user=request.user)
        .select_related("group")
    )

    return render(
        request,
        "groups/my_groups.html",
        {"memberships": memberships}
    )

@login_required
def edit_group(request, group_id):

    group = get_object_or_404(
        AjoGroup,
        id=group_id,
        owner=request.user
    )

    if group.status not in [
        AjoGroup.Status.DRAFT,
        AjoGroup.Status.OPEN,
    ]:
        messages.error(
            request,
            "This group can no longer be edited."
        )
        return redirect("groups:my_groups")

    if request.method == "POST":
        form = AjoGroupForm(request.POST, instance=group)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Your Ajo group has been updated."
            )

            return redirect("groups:my_groups")

    else:
        form = AjoGroupForm(instance=group)

    return render(
        request,
        "groups/edit_group.html",
        {"form": form, "group": group}
    )


def invitation_detail(request, token):

    group = get_object_or_404(
        AjoGroup,
        invitation_token=token
    )

    invitation_available = False
    unavailable_message = ""

    if group.status == AjoGroup.Status.CLOSED:
        unavailable_message = (
            "This group is currently closed to new members."
        )

    elif not group.invitation_active:
        unavailable_message = (
            "The group owner has temporarily disabled this invitation link."
        )

    elif group.status == AjoGroup.Status.DRAFT:
        unavailable_message = (
            "This group has not been published yet. "
            "Please contact the group owner."
        )

    elif group.status != AjoGroup.Status.OPEN:
        unavailable_message = (
            "This group is currently not accepting new members."
        )

    else:
        invitation_available = True

    return render(
        request,
        "groups/invitation_detail.html",
        {
            "group": group,
            "invitation_available": invitation_available,
            "unavailable_message": unavailable_message,
        }
    )

@login_required
@require_POST
def toggle_invitation(request, group_id):

    group = get_object_or_404(
        AjoGroup,
        id=group_id,
        owner=request.user
    )

    if group.status not in [
        AjoGroup.Status.DRAFT,
        AjoGroup.Status.OPEN,
    ]:
        messages.error(
            request,
            "Invitation settings cannot be changed for this group."
        )
        return redirect("groups:my_groups")

    group.invitation_active = not group.invitation_active
    group.save(update_fields=["invitation_active"])

    if group.invitation_active:
        messages.success(request, "Invitation link activated.")
    else:
        messages.success(request, "Invitation link deactivated.")

    return redirect("groups:my_groups")

@login_required
@require_POST
def publish_group(request, group_id):

    group = get_object_or_404(
        AjoGroup,
        id=group_id,
        owner=request.user
    )

    if group.status != AjoGroup.Status.DRAFT:
        messages.error(
            request,
            "Only draft groups can be published."
        )
        return redirect("groups:my_groups")

    with transaction.atomic():
        group.status = AjoGroup.Status.OPEN
        group.invitation_active = True
        group.save(
            update_fields=["status", "invitation_active", "updated_at"]
        )

    messages.success(
        request,
        f"{group.name} is now open for membership requests."
    )

    return redirect("groups:my_groups")

@login_required
@require_POST
def close_group(request, group_id):

    group = get_object_or_404(
        AjoGroup,
        id=group_id,
        owner=request.user
    )

    if group.status != AjoGroup.Status.OPEN:
        messages.error(request, "Only open groups can be closed.")
        return redirect("groups:my_groups")

    group.status = AjoGroup.Status.CLOSED
    group.invitation_active = False

    group.save(update_fields=[
        "status",
        "invitation_active",
        "updated_at",
    ])

    messages.success(request, "Your group has been closed.")

    return redirect("groups:my_groups")

@login_required
@require_POST
def reopen_group(request, group_id):

    group = get_object_or_404(
        AjoGroup,
        id=group_id,
        owner=request.user
    )

    if group.status != AjoGroup.Status.CLOSED:
        messages.error(request, "Only closed groups can be reopened.")
        return redirect("groups:my_groups")

    group.status = AjoGroup.Status.OPEN
    group.invitation_active = True

    group.save(update_fields=[
        "status",
        "invitation_active",
        "updated_at",
    ])

    messages.success(request, "Your group is open again.")

    return redirect("groups:my_groups")

@login_required
@require_POST
def delete_group(request, group_id):

    with transaction.atomic():

        group = get_object_or_404(
            AjoGroup.objects.select_for_update(),
            id=group_id,
            owner=request.user,
            status=AjoGroup.Status.DRAFT,
        )

        memberships = group.memberships.select_for_update()

        owner_membership = memberships.filter(
            user=request.user,
            role=GroupMembership.Role.OWNER,
            status=GroupMembership.Status.APPROVED,
        )

        if memberships.count() != 1 or not owner_membership.exists():
            messages.error(
                request,
                "This group cannot be deleted because it has membership history."
            )
            return redirect("groups:my_groups")

        group_name = group.name
        group.delete()

    messages.success(
        request,
        f"{group_name} was deleted successfully."
    )

    return redirect("groups:my_groups")

@login_required
@require_POST
def request_to_join(request, token):

    with transaction.atomic():

        group = get_object_or_404(
    AjoGroup.objects.select_for_update(),
    invitation_token=token
)

        if group.status == AjoGroup.Status.CLOSED:
            messages.error(
                request,
                "This group is closed to new members."
            )
            return redirect("groups:invitation_detail", token=token)

        if not group.invitation_active:
            messages.error(
                request,
                "The group owner has disabled this invitation link."
            )
            return redirect("groups:invitation_detail", token=token)

        if group.status != AjoGroup.Status.OPEN:
            messages.error(
                request,
                "This group is not currently accepting membership requests."
            )
            return redirect("groups:invitation_detail", token=token)

        if group.owner_id == request.user.id:
            messages.error(
                request,
                "You already own this group."
            )
            return redirect(
                "groups:invitation_detail",
                token=token
            )

        membership = GroupMembership.objects.filter(
            group=group,
            user=request.user
        ).first()

        if membership:
            if membership.status == GroupMembership.Status.APPROVED:
                messages.info(request, "You are already a member.")

            elif membership.status == GroupMembership.Status.PENDING:
                messages.info(request, "Your request is already pending.")

            elif membership.status == GroupMembership.Status.REMOVED:
                messages.error(
                    request,
                    "You were previously removed from this group. Please contact the group owner."
                )

            else:
                approved_count = group.memberships.filter(
                    status=GroupMembership.Status.APPROVED
                ).count()

                if approved_count >= group.max_members:
                    messages.error(request, "This group is already full.")
                else:
                    membership.status = GroupMembership.Status.PENDING
                    membership.reviewed_by = None
                    membership.reviewed_at = None
                    membership.save(update_fields=[
                        "status",
                        "reviewed_by",
                        "reviewed_at",
                    ])
                    messages.success(request, "Your new request has been submitted.")

        else:
            approved_count = group.memberships.filter(
                status=GroupMembership.Status.APPROVED
            ).count()

            if approved_count >= group.max_members:
                messages.error(request, "This group is already full.")
            else:
                GroupMembership.objects.create(
                    group=group,
                    user=request.user,
                    role=GroupMembership.Role.MEMBER,
                    status=GroupMembership.Status.PENDING,
                )

                messages.success(
                    request,
                    "Your request to join has been submitted."
                )

    return redirect("groups:invitation_detail", token=token)

@login_required
def manage_members(request, group_id):
    group = get_object_or_404(
        AjoGroup,
        id=group_id,
        owner=request.user
    )

    pending_members = (
        group.memberships
        .filter(
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.PENDING
        )
        .select_related("user")
    )

    approved_members = (
        group.memberships
        .filter(status=GroupMembership.Status.APPROVED)
        .select_related("user")
    )

    rejected_members = (
        group.memberships
        .filter(
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.REJECTED
        )
        .select_related("user", "reviewed_by")
    )
    removed_members = (
        group.memberships
        .filter(
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.REMOVED
        )
        .select_related("user", "removed_by")
    )
    membership_history = (
        GroupMembershipHistory.objects
        .filter(membership__group=group)
        .select_related("membership__user", "performed_by")
    )

    approved_count = approved_members.count()

    return render(
        request,
        "groups/manage_members.html",
        {
            "group": group,
            "pending_members": pending_members,
            "approved_members": approved_members,
            "removed_members": removed_members,
            "rejected_members": rejected_members,
            "membership_history": membership_history,
            "approved_count": approved_count,
            "available_slots": max(
                group.max_members - approved_count, 0
            ),
        }
    )


@login_required
@require_POST
def approve_member(request, group_id, membership_id):

    with transaction.atomic():

        group = get_object_or_404(
            AjoGroup.objects.select_for_update(),
            id=group_id,
            owner=request.user
        )

        membership = get_object_or_404(
            GroupMembership.objects.select_for_update(),
            id=membership_id,
            group=group,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.PENDING
        )

        approved_count = group.memberships.filter(
            status=GroupMembership.Status.APPROVED
        ).count()

        if approved_count >= group.max_members:
            messages.error(
                request,
                "Your group is full. You cannot approve another member."
            )
        else:
            membership.status = GroupMembership.Status.APPROVED
            membership.reviewed_by = request.user
            membership.reviewed_at = timezone.now()

            membership.save(update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at"
            ])

            # Add the approved member to the initial cycle
            # if the cycle has not started yet.
            cycle = AjoCycle.objects.filter(
                group=group,
                cycle_number=1,
                status__in=[
                    AjoCycle.Status.DRAFT,
                    AjoCycle.Status.SETUP,
                    AjoCycle.Status.READY,
                ],
            ).first()

            if cycle:
                CycleParticipant.objects.get_or_create(
                    cycle=cycle,
                    membership=membership,
                    defaults={
                        "status": CycleParticipant.Status.ACTIVE,
                    },
                )

            messages.success(
                request,
                f"{membership.user.full_name} has been approved."
            )

    return redirect("groups:manage_members", group_id=group.id)


@login_required
@require_POST
def reject_member(request, group_id, membership_id):

    with transaction.atomic():

        group = get_object_or_404(
            AjoGroup.objects.select_for_update(),
            id=group_id,
            owner=request.user
        )

        membership = get_object_or_404(
            GroupMembership.objects.select_for_update(),
            id=membership_id,
            group=group,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.PENDING
        )

        membership.status = GroupMembership.Status.REJECTED
        membership.reviewed_by = request.user
        membership.reviewed_at = timezone.now()

        membership.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at"
        ])

        messages.success(
            request,
            f"{membership.user.full_name}'s request has been rejected."
        )

    return redirect("groups:manage_members", group_id=group.id)
@login_required
@require_POST
def remove_member(request, group_id, membership_id):

    with transaction.atomic():

        group = get_object_or_404(
            AjoGroup.objects.select_for_update(),
            id=group_id,
            owner=request.user
        )

        allowed_statuses = [
            AjoGroup.Status.DRAFT,
            AjoGroup.Status.OPEN,
            AjoGroup.Status.CLOSED,
            AjoGroup.Status.READY,
        ]

        started_cycle_exists = group.cycles.filter(
            status__in=[
                AjoCycle.Status.ACTIVE,
                AjoCycle.Status.PAUSED,
                AjoCycle.Status.COMPLETED,
            ]
        ).exists()

        if group.status not in allowed_statuses or started_cycle_exists:
            messages.error(
                request,
                "Members cannot be removed after an Ajo cycle has started."
            )
            return redirect("groups:manage_members", group_id=group.id)

        membership = get_object_or_404(
            GroupMembership.objects.select_for_update(),
            id=membership_id,
            group=group,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.APPROVED
        )

        reason = request.POST.get("removal_reason", "").strip()[:255]
        member_name = membership.user.full_name

        # Update group membership.
        membership.status = GroupMembership.Status.REMOVED
        membership.removed_by = request.user
        membership.removed_at = timezone.now()
        membership.removal_reason = reason

        membership.save(update_fields=[
            "status",
            "removed_by",
            "removed_at",
            "removal_reason",
        ])

        # Find the member's participation in unstarted cycles.
        participants = CycleParticipant.objects.filter(
            membership=membership,
            cycle__group=group,
            cycle__status__in=[
                AjoCycle.Status.DRAFT,
                AjoCycle.Status.SETUP,
                AjoCycle.Status.READY,
            ],
            status__in=[
                CycleParticipant.Status.ACTIVE,
                CycleParticipant.Status.PENDING,
            ],
        )

        affected_cycle_ids = list(
            participants.values_list("cycle_id", flat=True)
        )

        # Withdraw participation and release payout positions.
        participants.update(
            status=CycleParticipant.Status.WITHDRAWN,
            payout_position=None,
        )

        # A changed participant list invalidates a READY rotation.
        group.cycles.filter(
            id__in=affected_cycle_ids,
            status=AjoCycle.Status.READY,
        ).update(
            status=AjoCycle.Status.SETUP,
            updated_at=timezone.now(),
        )

        # Preserve removal history.
        GroupMembershipHistory.objects.create(
            membership=membership,
            event_type=GroupMembershipHistory.EventType.REMOVED,
            performed_by=request.user,
            reason=reason,
        )

        messages.success(
            request,
            f"{member_name} has been removed from the group."
        )

    return redirect("groups:manage_members", group_id=group.id)

@login_required
@require_POST
def readd_member(request, group_id, membership_id):

    with transaction.atomic():

        group = get_object_or_404(
            AjoGroup.objects.select_for_update(),
            id=group_id,
            owner=request.user
        )

        allowed_statuses = [
            AjoGroup.Status.DRAFT,
            AjoGroup.Status.OPEN,
            AjoGroup.Status.CLOSED,
            AjoGroup.Status.READY,
        ]

        started_cycle_exists = group.cycles.filter(
            status__in=[
                AjoCycle.Status.ACTIVE,
                AjoCycle.Status.PAUSED,
                AjoCycle.Status.COMPLETED,
            ]
        ).exists()

        if group.status not in allowed_statuses or started_cycle_exists:
            messages.error(
                request,
                "Members cannot be re-added after an Ajo cycle has started."
            )
            return redirect("groups:manage_members", group_id=group.id)

        membership = get_object_or_404(
            GroupMembership.objects.select_for_update(),
            id=membership_id,
            group=group,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.REMOVED
        )

        approved_count = group.memberships.filter(
            status=GroupMembership.Status.APPROVED
        ).count()

        if approved_count >= group.max_members:
            messages.error(
                request,
                "Your group is full. You cannot re-add this member yet."
            )
            return redirect("groups:manage_members", group_id=group.id)

        member_name = membership.user.full_name

        # Restore group membership.
        membership.status = GroupMembership.Status.APPROVED
        membership.reviewed_by = request.user
        membership.reviewed_at = timezone.now()

        # Clear current removal fields.
        # Historical removal details remain in GroupMembershipHistory.
        membership.removed_by = None
        membership.removed_at = None
        membership.removal_reason = ""

        membership.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "removed_by",
            "removed_at",
            "removal_reason",
        ])

        # Find previously withdrawn participation in unstarted cycles.
        participants = CycleParticipant.objects.filter(
            membership=membership,
            cycle__group=group,
            cycle__status__in=[
                AjoCycle.Status.DRAFT,
                AjoCycle.Status.SETUP,
                AjoCycle.Status.READY,
            ],
            status=CycleParticipant.Status.WITHDRAWN,
        )

        # Identify cycles affected by this member rejoining.
        affected_cycle_ids = list(
            participants.values_list("cycle_id", flat=True)
        )

        # Restore participation without restoring an old payout position.
        participants.update(
            status=CycleParticipant.Status.ACTIVE,
            payout_position=None,
        )

        # The participant list has changed, so the rotation
        # must be reviewed again.
        group.cycles.filter(
            id__in=affected_cycle_ids,
            status=AjoCycle.Status.READY,
        ).update(
            status=AjoCycle.Status.SETUP,
            updated_at=timezone.now(),
        )
        # Preserve rejoining history.
        GroupMembershipHistory.objects.create(
            membership=membership,
            event_type=GroupMembershipHistory.EventType.REJOINED,
            performed_by=request.user,
            reason="Re-added by group owner.",
        )

        messages.success(
            request,
            f"{member_name} has been added back to the group."
        )

    return redirect("groups:manage_members", group_id=group.id)