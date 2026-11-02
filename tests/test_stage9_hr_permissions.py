from django.contrib.auth.models import Permission
from django.test import TestCase

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.accounts.services import (
    has_school_permission,
    is_school_permission_allowed,
    school_assignable_permissions,
)
from apps.payroll.api.hr_serializers import EmployeeContractSerializer
from apps.staff.models import Teacher
from apps.tenants.models import Branch, School


class Stage9PayrollPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+15550101001",
            password="StrongPassword123!",
            first_name="School",
            last_name="Owner",
        )
        cls.school = School.objects.create(
            owner=cls.owner,
            code="STAGE9SEC",
            name="Stage Nine Security School",
            status=School.Status.ACTIVE,
        )
        cls.user = User.objects.create_user(
            phone="+15550101002",
            password="StrongPassword123!",
            first_name="Payroll",
            last_name="Reviewer",
        )
        membership = SchoolMembership.objects.create(
            school=cls.school,
            user=cls.user,
            status=SchoolMembership.Status.ACTIVE,
        )
        cls.role = SchoolRole.objects.create(
            school=cls.school,
            code="payroll-reviewer",
            name="مراجع الرواتب",
        )
        MembershipRole.objects.create(membership=membership, role=cls.role)

    def test_custom_payroll_action_permissions_are_assignable_and_independent(self):
        approve = Permission.objects.get(
            content_type__app_label="payroll",
            codename="approve_payrollrun",
        )
        post = Permission.objects.get(
            content_type__app_label="payroll",
            codename="post_payrollrun",
        )
        disburse = Permission.objects.get(
            content_type__app_label="payroll",
            codename="disburse_payrollrun",
        )
        self.assertTrue(is_school_permission_allowed(approve))
        self.assertTrue(school_assignable_permissions().filter(pk=approve.pk).exists())
        self.role.permissions.add(approve)

        self.assertTrue(has_school_permission(
            user=self.user,
            school=self.school,
            permission="payroll.approve_payrollrun",
        ))
        self.assertFalse(has_school_permission(
            user=self.user,
            school=self.school,
            permission="payroll.post_payrollrun",
        ))
        self.assertFalse(has_school_permission(
            user=self.user,
            school=self.school,
            permission="payroll.disburse_payrollrun",
        ))
        self.assertTrue(is_school_permission_allowed(post))
        self.assertTrue(is_school_permission_allowed(disburse))

    def test_contract_serializer_rejects_a_branch_other_than_employee_branch(self):
        branch_a = Branch.objects.create(
            school=self.school, code="BRANCH_A", name="الفرع أ",
        )
        branch_b = Branch.objects.create(
            school=self.school, code="BRANCH_B", name="الفرع ب",
        )
        teacher = Teacher.objects.create(
            school=self.school,
            branch=branch_a,
            user=self.user,
            specialization="رياضيات",
        )

        invalid = EmployeeContractSerializer(
            data={
                "branch": str(branch_b.pk),
                "teacher": str(teacher.pk),
                "contract_number": "CNT-BRANCH-INVALID",
                "start_date": "2026-11-01",
                "basic_salary": "1000.00",
            },
            context={"school": self.school},
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("branch", invalid.errors)

        valid = EmployeeContractSerializer(
            data={
                "teacher": str(teacher.pk),
                "contract_number": "CNT-BRANCH-VALID",
                "start_date": "2026-11-01",
                "basic_salary": "1000.00",
            },
            context={"school": self.school},
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.validated_data["branch"].pk, branch_a.pk)
