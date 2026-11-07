from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError, transaction
from .models import (
    AjoGroup,
    GroupMembership,
    GroupMembershipHistory,
    AjoCycle,
    CycleParticipant
)


User = get_user_model()


class GroupTestBase(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            full_name="Group Owner",
            password="StrongPassword123!"
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            full_name="Group Member",
            password="StrongPassword123!"
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            full_name="Other User",
            password="StrongPassword123!"
        )

        self.group = AjoGroup.objects.create(
            owner=self.owner,
            name="Test Ajo Group",
            contribution_amount=Decimal("10000.00"),
            frequency=AjoGroup.Frequency.MONTHLY,
            max_members=3,
            payout_method=AjoGroup.PayoutMethod.MANUAL,
            status=AjoGroup.Status.OPEN,
        )

        self.owner_membership = GroupMembership.objects.create(
            group=self.group,
            user=self.owner,
            role=GroupMembership.Role.OWNER,
            status=GroupMembership.Status.APPROVED,
            reviewed_by=self.owner,
            reviewed_at=timezone.now(),
        )

        self.member_membership = GroupMembership.objects.create(
            group=self.group,
            user=self.member,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.PENDING,
        )
        self.cycle = AjoCycle.objects.create(
            group=self.group,
            cycle_number=1,
            onboarding_type=AjoCycle.OnboardingType.NEW,
            contribution_amount=self.group.contribution_amount,
            frequency=self.group.frequency,
            payout_method=self.group.payout_method,
            start_date=self.group.start_date,
            status=AjoCycle.Status.SETUP,
        )

        CycleParticipant.objects.create(
            cycle=self.cycle,
            membership=self.owner_membership,
            status=CycleParticipant.Status.ACTIVE,
        )

        self.client.force_login(self.owner)


class GroupModelTests(GroupTestBase):

    def test_group_is_created(self):
        self.assertEqual(self.group.name, "Test Ajo Group")
        self.assertEqual(self.group.owner, self.owner)

    def test_owner_membership_is_approved(self):
        self.assertEqual(
            self.owner_membership.status,
            GroupMembership.Status.APPROVED
        )

        self.assertEqual(
            self.owner_membership.role,
            GroupMembership.Role.OWNER
        )

    def test_membership_starts_as_pending(self):
        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.PENDING
        )

    def test_group_has_unique_user_membership(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GroupMembership.objects.create(
                    group=self.group,
                    user=self.member,
                    role=GroupMembership.Role.MEMBER,
                    status=GroupMembership.Status.APPROVED,
                )


class MembershipManagementTests(GroupTestBase):

    def test_owner_can_view_members(self):
        response = self.client.get(
            reverse(
                "groups:manage_members",
                args=[self.group.id]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.full_name)

    def test_non_owner_cannot_manage_members(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "groups:manage_members",
                args=[self.group.id]
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_approve_member(self):
        response = self.client.post(
            reverse(
                "groups:approve_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.APPROVED
        )

        self.assertEqual(
            self.member_membership.reviewed_by,
            self.owner
        )

        self.assertRedirects(
            response,
            reverse("groups:manage_members", args=[self.group.id])
        )

        participant = CycleParticipant.objects.get(
            cycle=self.cycle,
            membership=self.member_membership,
        )

        self.assertEqual(
            participant.status,
            CycleParticipant.Status.ACTIVE,
        )

    def test_owner_can_reject_member(self):
        response = self.client.post(
            reverse(
                "groups:reject_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.REJECTED
        )

        self.assertEqual(
            self.member_membership.reviewed_by,
            self.owner
        )

    def test_approval_is_blocked_when_group_is_full(self):

        GroupMembership.objects.create(
            group=self.group,
            user=self.other_user,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.APPROVED,
        )

        self.group.max_members = 2
        self.group.save()

        response = self.client.post(
            reverse(
                "groups:approve_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.PENDING
        )

        self.assertFalse(
            CycleParticipant.objects.filter(
                cycle=self.cycle,
                membership=self.member_membership,
            ).exists()
        )

class MembershipRemovalTests(GroupTestBase):

    def setUp(self):
        super().setUp()

        self.member_membership.status = GroupMembership.Status.APPROVED
        self.member_membership.reviewed_by = self.owner
        self.member_membership.reviewed_at = timezone.now()
        self.member_membership.save()

        self.member_participant = CycleParticipant.objects.create(
            cycle=self.cycle,
            membership=self.member_membership,
            status=CycleParticipant.Status.ACTIVE,
            payout_position=2,
        )

    def test_owner_can_remove_approved_member(self):
        response = self.client.post(
            reverse(
                "groups:remove_member",
                args=[self.group.id, self.member_membership.id]
            ),
            {"removal_reason": "Failed to meet group requirements."}
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.REMOVED
        )

        self.assertEqual(
            self.member_membership.removed_by,
            self.owner
        )

        self.assertEqual(
            self.member_membership.removal_reason,
            "Failed to meet group requirements."
        )

        self.assertTrue(
            GroupMembershipHistory.objects.filter(
                membership=self.member_membership,
                event_type=GroupMembershipHistory.EventType.REMOVED
            ).exists()
        )

        self.member_participant.refresh_from_db()

        self.assertEqual(
            self.member_participant.status,
            CycleParticipant.Status.WITHDRAWN
        )

        self.assertIsNone(
            self.member_participant.payout_position
        )

    def test_removal_resets_ready_cycle_to_setup(self):
        self.cycle.status = AjoCycle.Status.READY
        self.cycle.save()

        self.client.post(
            reverse(
                "groups:remove_member",
                args=[self.group.id, self.member_membership.id]
            ),
            {"removal_reason": "Testing cycle reset."}
        )

        self.cycle.refresh_from_db()

        self.assertEqual(
            self.cycle.status,
            AjoCycle.Status.SETUP
        )

    def test_removal_invalidates_confirmed_rotation(self):
    # Prepare a confirmed rotation.
        self.cycle.status = AjoCycle.Status.READY
        self.cycle.rotation_confirmed_at = timezone.now()
        self.cycle.rotation_confirmed_by = self.owner
        self.cycle.save()

        # Give the owner an existing payout position.
        CycleParticipant.objects.update_or_create(
            cycle=self.cycle,
            membership=self.owner_membership,
            defaults={
                "status": CycleParticipant.Status.ACTIVE,
                "payout_position": 1,
            }
        )

        self.member_participant.payout_position = 2
        self.member_participant.save()

        # Remove the member.
        self.client.post(
            reverse(
                "groups:remove_member",
                args=[self.group.id, self.member_membership.id]
            ),
            {"removal_reason": "Testing rotation invalidation."}
        )

        self.cycle.refresh_from_db()
        self.member_participant.refresh_from_db()

        # The cycle must return to SETUP.
        self.assertEqual(
            self.cycle.status,
            AjoCycle.Status.SETUP
        )

        # Previous confirmation must be cleared.
        self.assertIsNone(self.cycle.rotation_confirmed_at)
        self.assertIsNone(self.cycle.rotation_confirmed_by)

        # The removed member must be withdrawn.
        self.assertEqual(
            self.member_participant.status,
            CycleParticipant.Status.WITHDRAWN
        )

        # All remaining active participants must lose old positions.
        active_participants = CycleParticipant.objects.filter(
            cycle=self.cycle,
            status=CycleParticipant.Status.ACTIVE
        )

        self.assertTrue(active_participants.exists())

        for participant in active_participants:
            self.assertIsNone(participant.payout_position)

    def test_removal_is_blocked_when_cycle_is_active(self):
        self.cycle.status = AjoCycle.Status.ACTIVE
        self.cycle.save()

        self.client.post(
            reverse(
                "groups:remove_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.member_participant.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.APPROVED
        )

        self.assertEqual(
            self.member_participant.status,
            CycleParticipant.Status.ACTIVE
        )
    def test_removal_is_blocked_after_cycle_starts(self):
        self.group.status = AjoGroup.Status.ACTIVE
        self.group.save()

        self.client.post(
            reverse(
                "groups:remove_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.APPROVED
        )

    def test_owner_cannot_remove_themselves(self):
        response = self.client.post(
            reverse(
                "groups:remove_member",
                args=[self.group.id, self.owner_membership.id]
            )
        )

        self.owner_membership.refresh_from_db()

        self.assertEqual(
            self.owner_membership.status,
            GroupMembership.Status.APPROVED
        )


class MembershipRejoinTests(GroupTestBase):

    def setUp(self):
        super().setUp()

        self.member_membership.status = GroupMembership.Status.REMOVED
        self.member_membership.removed_by = self.owner
        self.member_membership.removed_at = timezone.now()
        self.member_membership.removal_reason = "Previous removal."
        self.member_membership.save()

        self.member_participant = CycleParticipant.objects.create(
            cycle=self.cycle,
            membership=self.member_membership,
            status=CycleParticipant.Status.WITHDRAWN,
            payout_position=None,
        )

    def test_owner_can_readd_removed_member(self):
        response = self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.APPROVED
        )

        self.assertEqual(
            self.member_membership.reviewed_by,
            self.owner
        )

        self.assertIsNone(self.member_membership.removed_at)

        self.assertTrue(
            GroupMembershipHistory.objects.filter(
                membership=self.member_membership,
                event_type=GroupMembershipHistory.EventType.REJOINED
            ).exists()
        )

        self.member_participant.refresh_from_db()

        self.assertEqual(
            self.member_participant.status,
            CycleParticipant.Status.ACTIVE
        )

        self.assertIsNone(
            self.member_participant.payout_position
        )

    def test_rejoining_resets_ready_cycle_to_setup(self):
        self.cycle.status = AjoCycle.Status.READY
        self.cycle.save()

        self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.cycle.refresh_from_db()

        self.assertEqual(
            self.cycle.status,
            AjoCycle.Status.SETUP
        )

    def test_rejoining_invalidates_confirmed_rotation(self):
    # Prepare a confirmed rotation.
        self.cycle.status = AjoCycle.Status.READY
        self.cycle.rotation_confirmed_at = timezone.now()
        self.cycle.rotation_confirmed_by = self.owner
        self.cycle.save()

        # Give the owner an existing payout position.
        CycleParticipant.objects.update_or_create(
            cycle=self.cycle,
            membership=self.owner_membership,
            defaults={
                "status": CycleParticipant.Status.ACTIVE,
                "payout_position": 1,
            }
        )

        # Re-add the member.
        self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.cycle.refresh_from_db()
        self.member_participant.refresh_from_db()

        # The cycle must return to SETUP.
        self.assertEqual(
            self.cycle.status,
            AjoCycle.Status.SETUP
        )

        # Previous confirmation must be cleared.
        self.assertIsNone(self.cycle.rotation_confirmed_at)
        self.assertIsNone(self.cycle.rotation_confirmed_by)

        # The member must be active again.
        self.assertEqual(
            self.member_participant.status,
            CycleParticipant.Status.ACTIVE
        )

        # All active participants must lose old positions.
        active_participants = CycleParticipant.objects.filter(
            cycle=self.cycle,
            status=CycleParticipant.Status.ACTIVE
        )

        self.assertTrue(active_participants.exists())

        for participant in active_participants:
            self.assertIsNone(participant.payout_position)

    def test_rejoining_is_blocked_when_cycle_is_active(self):
        self.cycle.status = AjoCycle.Status.ACTIVE
        self.cycle.save()

        self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()
        self.member_participant.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.REMOVED
        )

        self.assertEqual(
            self.member_participant.status,
            CycleParticipant.Status.WITHDRAWN
        )

    def test_readding_is_blocked_when_group_is_full(self):

        GroupMembership.objects.create(
            group=self.group,
            user=self.other_user,
            role=GroupMembership.Role.MEMBER,
            status=GroupMembership.Status.APPROVED,
        )

        self.group.max_members = 2
        self.group.save()

        response = self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.REMOVED
        )

        self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.REMOVED
        )

    def test_readding_is_blocked_after_cycle_starts(self):
        self.group.status = AjoGroup.Status.ACTIVE
        self.group.save()

        self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.status,
            GroupMembership.Status.REMOVED
        )

    def test_removal_history_is_preserved_after_rejoining(self):
        GroupMembershipHistory.objects.create(
            membership=self.member_membership,
            event_type=GroupMembershipHistory.EventType.REMOVED,
            performed_by=self.owner,
            reason="Previous removal."
        )

        self.client.post(
            reverse(
                "groups:readd_member",
                args=[self.group.id, self.member_membership.id]
            )
        )

        self.assertEqual(
            GroupMembershipHistory.objects.filter(
                membership=self.member_membership
            ).count(),
            2
        )

class CycleCreationTests(GroupTestBase):

    def setUp(self):
        super().setUp()

        # Approve the second member.
        self.member_membership.status = GroupMembership.Status.APPROVED
        self.member_membership.reviewed_by = self.owner
        self.member_membership.reviewed_at = timezone.now()
        self.member_membership.save()

        # Create the initial cycle.
        # Reuse the initial cycle created for the group.
        self.cycle = AjoCycle.objects.get(
            group=self.group,
            cycle_number=1,
        )

        # Mark it as completed so the next cycle can be created.
        self.cycle.status = AjoCycle.Status.COMPLETED
        self.cycle.save(update_fields=["status"])

        # Ensure both members are participants in the completed cycle.
        CycleParticipant.objects.update_or_create(
            cycle=self.cycle,
            membership=self.owner_membership,
            defaults={
                "status": CycleParticipant.Status.ACTIVE,
                "payout_position": 1,
            },
        )

        CycleParticipant.objects.update_or_create(
            cycle=self.cycle,
            membership=self.member_membership,
            defaults={
                "status": CycleParticipant.Status.ACTIVE,
                "payout_position": 2,
            },
        )

        self.create_url = reverse(
            "groups:create_cycle",
            args=[self.group.id]
        )

        self.valid_data = {
            "contribution_amount": "15000.00",
            "frequency": AjoGroup.Frequency.WEEKLY,
            "payout_method": AjoGroup.PayoutMethod.MANUAL,
            "start_date": "",
            "participants": [
                self.owner_membership.id,
                self.member_membership.id,
            ],
        }

    def test_owner_can_create_next_cycle(self):

        response = self.client.post(
            self.create_url,
            self.valid_data
        )

        self.assertRedirects(
            response,
            reverse("groups:cycle_overview", args=[self.group.id])
        )

        new_cycle = AjoCycle.objects.get(
            group=self.group,
            cycle_number=2
        )

        self.assertEqual(
            new_cycle.status,
            AjoCycle.Status.DRAFT
        )

        self.assertEqual(
            new_cycle.contribution_amount,
            Decimal("15000.00")
        )

        self.assertEqual(
            new_cycle.frequency,
            AjoGroup.Frequency.WEEKLY
        )

        self.assertEqual(
            new_cycle.participants.count(),
            2
        )

    def test_cycle_number_increments_automatically(self):

        self.cycle.cycle_number = 3
        self.cycle.save()

        response = self.client.post(
            self.create_url,
            self.valid_data
        )

        self.assertTrue(
            AjoCycle.objects.filter(
                group=self.group,
                cycle_number=4
            ).exists()
        )

    def test_cannot_create_cycle_before_previous_is_completed(self):

        self.cycle.status = AjoCycle.Status.ACTIVE
        self.cycle.save()

        response = self.client.post(
            self.create_url,
            self.valid_data
        )

        self.assertFalse(
            AjoCycle.objects.filter(
                group=self.group,
                cycle_number=2
            ).exists()
        )

    def test_non_owner_cannot_create_cycle(self):

        self.client.force_login(self.member)

        response = self.client.post(
            self.create_url,
            self.valid_data
        )

        self.assertEqual(response.status_code, 404)

        self.assertFalse(
            AjoCycle.objects.filter(
                group=self.group,
                cycle_number=2
            ).exists()
        )

    def test_cycle_requires_at_least_two_participants(self):

        invalid_data = self.valid_data.copy()

        invalid_data["participants"] = [
            self.owner_membership.id
        ]

        response = self.client.post(
            self.create_url,
            invalid_data
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            AjoCycle.objects.filter(
                group=self.group,
                cycle_number=2
            ).exists()
        )

    def test_new_cycle_participants_start_without_positions(self):

        self.client.post(
            self.create_url,
            self.valid_data
        )

        new_cycle = AjoCycle.objects.get(
            group=self.group,
            cycle_number=2
        )

        self.assertFalse(
            new_cycle.participants.filter(
                payout_position__isnull=False
            ).exists()
        )


class RotationManagementTests(GroupTestBase):

    def setUp(self):
        super().setUp()

        # Approve the second member.
        self.member_membership.status = GroupMembership.Status.APPROVED
        self.member_membership.reviewed_by = self.owner
        self.member_membership.reviewed_at = timezone.now()
        self.member_membership.save()

        # Reuse the initial cycle.
        self.cycle = AjoCycle.objects.get(
            group=self.group,
            cycle_number=1,
        )

        self.cycle.status = AjoCycle.Status.SETUP
        self.cycle.payout_method = AjoGroup.PayoutMethod.MANUAL
        self.cycle.rotation_confirmed_at = None
        self.cycle.rotation_confirmed_by = None
        self.cycle.save()

        # Ensure both members participate in the cycle.
        CycleParticipant.objects.update_or_create(
            cycle=self.cycle,
            membership=self.owner_membership,
            defaults={
                "status": CycleParticipant.Status.ACTIVE,
                "payout_position": None,
            },
        )

        CycleParticipant.objects.update_or_create(
            cycle=self.cycle,
            membership=self.member_membership,
            defaults={
                "status": CycleParticipant.Status.ACTIVE,
                "payout_position": None,
            },
        )

        self.client.force_login(self.owner)

        self.rotation_url = reverse(
            "groups:manage_rotation",
            args=[self.group.id, self.cycle.id],
        )

        self.random_url = reverse(
            "groups:generate_random_rotation",
            args=[self.group.id, self.cycle.id],
        )

        self.confirm_url = reverse(
            "groups:confirm_rotation",
            args=[self.group.id, self.cycle.id],
        )

        self.participant_ids = list(
            self.cycle.participants.filter(
                status=CycleParticipant.Status.ACTIVE
            ).values_list("id", flat=True)
        )

    def arrange_manually(self, ordered_ids=None):

        if ordered_ids is None:
            ordered_ids = self.participant_ids

        return self.client.post(
            self.rotation_url,
            {
                "participant_order": [
                    str(participant_id)
                    for participant_id in ordered_ids
                ]
            },
        )

    def test_owner_can_assign_manual_positions(self):

        ordered_ids = list(reversed(self.participant_ids))

        response = self.arrange_manually(ordered_ids)

        self.assertEqual(response.status_code, 302)

        participants = list(
            self.cycle.participants.filter(
                status=CycleParticipant.Status.ACTIVE
            ).order_by("payout_position")
        )

        self.assertEqual(
            [p.id for p in participants],
            ordered_ids,
        )

        self.assertEqual(
            [p.payout_position for p in participants],
            [1, 2],
        )

    def test_non_owner_cannot_manage_rotation(self):

        self.client.force_login(self.member)

        response = self.client.get(self.rotation_url)

        self.assertEqual(response.status_code, 404)

    def test_random_rotation_generates_positions(self):

        self.cycle.payout_method = AjoGroup.PayoutMethod.RANDOM
        self.cycle.save(update_fields=["payout_method"])

        response = self.client.post(self.random_url)

        self.assertEqual(response.status_code, 302)

        positions = list(
            self.cycle.participants.filter(
                status=CycleParticipant.Status.ACTIVE
            ).values_list("payout_position", flat=True)
        )

        self.assertEqual(sorted(positions), [1, 2])

    def test_random_rotation_can_be_manually_adjusted(self):

        self.cycle.payout_method = AjoGroup.PayoutMethod.RANDOM
        self.cycle.save(update_fields=["payout_method"])

        self.client.post(self.random_url)

        ordered_ids = list(reversed(self.participant_ids))

        response = self.arrange_manually(ordered_ids)

        self.assertEqual(response.status_code, 302)

        participants = list(
            self.cycle.participants.filter(
                status=CycleParticipant.Status.ACTIVE
            ).order_by("payout_position")
        )

        self.assertEqual(
            [p.id for p in participants],
            ordered_ids,
        )

    def test_random_generation_requires_random_method(self):

        response = self.client.post(self.random_url)

        self.assertEqual(response.status_code, 404)

    def test_owner_can_confirm_rotation(self):

        self.arrange_manually()

        response = self.client.post(self.confirm_url)

        self.assertEqual(response.status_code, 302)

        self.cycle.refresh_from_db()

        self.assertEqual(
            self.cycle.status,
            AjoCycle.Status.READY,
        )

        self.assertIsNotNone(
            self.cycle.rotation_confirmed_at
        )

        self.assertEqual(
            self.cycle.rotation_confirmed_by,
            self.owner,
        )

    def test_cannot_confirm_rotation_without_positions(self):

        response = self.client.post(self.confirm_url)

        self.assertEqual(response.status_code, 302)

        self.cycle.refresh_from_db()

        self.assertIsNone(
            self.cycle.rotation_confirmed_at
        )

        self.assertNotEqual(
            self.cycle.status,
            AjoCycle.Status.READY,
        )

    def test_confirmed_rotation_cannot_be_changed(self):

        self.arrange_manually()

        self.client.post(self.confirm_url)

        original_positions = dict(
            self.cycle.participants.values_list(
                "id",
                "payout_position",
            )
        )

        self.arrange_manually(
            list(reversed(self.participant_ids))
        )

        updated_positions = dict(
            self.cycle.participants.values_list(
                "id",
                "payout_position",
            )
        )

        self.assertEqual(
            original_positions,
            updated_positions,
        )

    def test_confirmed_random_rotation_cannot_be_regenerated(self):

        self.cycle.payout_method = AjoGroup.PayoutMethod.RANDOM
        self.cycle.save(update_fields=["payout_method"])

        self.client.post(self.random_url)
        self.client.post(self.confirm_url)

        original_positions = dict(
            self.cycle.participants.values_list(
                "id",
                "payout_position",
            )
        )

        self.client.post(self.random_url)

        updated_positions = dict(
            self.cycle.participants.values_list(
                "id",
                "payout_position",
            )
        )

        self.assertEqual(
            original_positions,
            updated_positions,
        )

