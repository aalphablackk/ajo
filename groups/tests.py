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

    def test_creating_group_creates_first_cycle(self):
        response = self.client.post(
            reverse("groups:create_group"),
            {
                "name": "New Test Ajo",
                "description": "Testing automatic cycle creation",
                "contribution_amount": "25000.00",
                "frequency": "monthly",
                "max_members": 6,
                "start_date": "",
                "payout_method": "manual",
            },
        )

        self.assertRedirects(
            response,
            reverse("groups:my_groups"),
        )

        group = AjoGroup.objects.get(name="New Test Ajo")

        cycle = AjoCycle.objects.get(
            group=group,
            cycle_number=1,
        )

        self.assertEqual(
            cycle.contribution_amount,
            Decimal("25000.00"),
        )

        self.assertEqual(
            cycle.frequency,
            AjoCycle._meta.get_field("frequency").default
            if False else "monthly",
        )

        self.assertEqual(
            cycle.status,
            AjoCycle.Status.DRAFT,
        )

        owner_membership = GroupMembership.objects.get(
            group=group,
            user=self.owner,
        )

        self.assertTrue(
            CycleParticipant.objects.filter(
                cycle=cycle,
                membership=owner_membership,
                status=CycleParticipant.Status.ACTIVE,
            ).exists()
        )
