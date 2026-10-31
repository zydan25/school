"""Regression tests for active school context resolution in mobile/API requests."""
from datetime import timedelta
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounts.api_permissions import resolve_active_school
from apps.accounts.models import SchoolMembership, User
from apps.tenants.models import School
from apps.tenants.services import resolve_school_for_user


class SchoolContextSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+967770009991",
            password="Strong-Test-Password-991",
            first_name="اختبار",
            last_name="السياق",
        )
        self.school_a = School.objects.create(
            owner=self.user,
            code="CTX-A",
            name="مدرسة السياق أ",
            status=School.Status.ACTIVE,
        )
        self.school_b = School.objects.create(
            owner=self.user,
            code="CTX-B",
            name="مدرسة السياق ب",
            status=School.Status.ACTIVE,
        )
        self.membership_a = SchoolMembership.objects.create(
            school=self.school_a,
            user=self.user,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=timezone.now(),
            is_default=True,
        )
        self.membership_b = SchoolMembership.objects.create(
            school=self.school_b,
            user=self.user,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )

    def make_request(self, headers=None, context_error=None):
        return SimpleNamespace(
            user=self.user,
            school=None,
            school_context_error=context_error,
            headers=headers or {},
            query_params={},
        )

    def test_explicit_school_header_selects_a_valid_membership(self):
        request = self.make_request(headers={"X-School-ID": str(self.school_b.pk)})
        self.assertEqual(resolve_active_school(request), self.school_b)

    def test_multiple_memberships_do_not_pick_the_first_membership(self):
        self.membership_a.is_default = False
        self.membership_a.save(update_fields=["is_default", "updated_at"])
        self.assertIsNone(resolve_active_school(self.make_request()))

    def test_default_membership_is_selected(self):
        self.assertEqual(resolve_active_school(self.make_request()), self.school_a)

    def test_expired_membership_is_not_resolved_or_switchable(self):
        expired_user = User.objects.create_user(
            phone="+967770009992",
            password="Strong-Test-Password-992",
            first_name="عضوية",
            last_name="منتهية",
        )
        expired_school = School.objects.create(
            owner=expired_user,
            code="CTX-EXP",
            name="مدرسة منتهية",
            status=School.Status.ACTIVE,
        )
        now = timezone.now()
        SchoolMembership.objects.create(
            school=expired_school,
            user=expired_user,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=now - timedelta(days=3),
            expires_at=now - timedelta(days=1),
        )
        request = SimpleNamespace(
            user=expired_user,
            school=None,
            school_context_error=None,
            headers={},
            query_params={},
        )
        self.assertIsNone(resolve_active_school(request))
        with self.assertRaises(PermissionDenied):
            resolve_school_for_user(user=expired_user, school_code=expired_school.code)

    def test_middleware_context_error_fails_closed(self):
        request = self.make_request(
            headers={"X-School-ID": str(self.school_a.pk)},
            context_error="school selection is invalid",
        )
        self.assertIsNone(resolve_active_school(request))
