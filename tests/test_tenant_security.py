from datetime import date

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.contrib.sessions.middleware import SessionMiddleware

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.accounts.services import has_school_permission
from apps.academics.models import AcademicYear
from apps.tenants.middleware import SchoolContextMiddleware
from apps.tenants.models import Branch, School


class TenantSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_a = User.objects.create_user(
            phone="+967777000001", password="Strong-Password-01",
            first_name="أحمد", last_name="الأول", email="owner-a@example.test",
        )
        cls.owner_b = User.objects.create_user(
            phone="+967777000002", password="Strong-Password-02",
            first_name="خالد", last_name="الثاني", email="owner-b@example.test",
        )
        cls.school_a = School.objects.create(owner=cls.owner_a, code="SCH001", name="مدرسة النور", status=School.Status.ACTIVE)
        cls.school_b = School.objects.create(owner=cls.owner_b, code="SCH002", name="مدرسة المستقبل", status=School.Status.ACTIVE)
        cls.membership_a = SchoolMembership.objects.create(school=cls.school_a, user=cls.owner_a, status=SchoolMembership.Status.ACTIVE, is_default=True)
        cls.membership_b = SchoolMembership.objects.create(school=cls.school_b, user=cls.owner_b, status=SchoolMembership.Status.ACTIVE, is_default=True)

    def build_request(self, user, school_code):
        request = RequestFactory().get("/school-admin/", HTTP_X_SCHOOL_CODE=school_code)
        SessionMiddleware(lambda _request: None).process_request(request)
        request.user = user
        SchoolContextMiddleware(lambda _request: None).process_request(request)
        return request

    def test_user_phone_rejects_malformed_international_numbers(self):
        user = User(phone="++967777000099", first_name="اختبار", last_name="هاتف")
        with self.assertRaises(ValidationError):
            user.full_clean(exclude=["password", "last_login", "groups", "user_permissions"])

    def test_header_cannot_select_school_without_membership(self):
        request = self.build_request(self.owner_a, "SCH002")
        self.assertIsNone(request.school)
        self.assertIn("لا تملك عضوية", request.school_context_error)

    def test_member_can_select_own_school(self):
        request = self.build_request(self.owner_a, "SCH001")
        self.assertEqual(request.school, self.school_a)
        self.assertEqual(request.school_membership, self.membership_a)

    def test_header_selects_only_the_matching_membership(self):
        SchoolMembership.objects.create(school=self.school_b, user=self.owner_a, status=SchoolMembership.Status.ACTIVE)
        request = self.build_request(self.owner_a, "SCH002")
        self.assertEqual(request.school, self.school_b)

    def test_permission_does_not_cross_school(self):
        role = SchoolRole.objects.create(school=self.school_b, code="registrar", name="مسجل")
        permission = Permission.objects.get(content_type__app_label="academics", codename="view_academicyear")
        role.permissions.add(permission)
        MembershipRole.objects.create(membership=self.membership_b, role=role)
        self.assertFalse(has_school_permission(user=self.owner_a, school=self.school_a, permission="academics.view_academicyear"))
        self.assertTrue(has_school_permission(user=self.owner_b, school=self.school_b, permission="academics.view_academicyear"))

    def test_role_from_another_school_is_rejected(self):
        role_b = SchoolRole.objects.create(school=self.school_b, code="teacher", name="معلم")
        with self.assertRaises(ValidationError):
            MembershipRole.objects.create(membership=self.membership_a, role=role_b)

    def test_branch_from_another_school_is_rejected_by_tenant_model(self):
        branch_b = Branch.objects.create(school=self.school_b, code="MAIN", name="الرئيسي", is_main=True)
        year = AcademicYear(
            school=self.school_a, branch=branch_b, name="2026-2027", code="2026-27",
            starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30),
        )
        with self.assertRaises(ValidationError):
            year.full_clean()
