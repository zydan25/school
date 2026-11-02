from django.contrib.auth.models import Permission
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.accounts.services import (
    has_school_permission,
    is_school_permission_allowed,
    school_assignable_permissions,
)
from apps.payroll.api.hr_serializers import EmployeeContractSerializer
from apps.payroll.models import PayrollRun
from apps.staff.models import LeaveRequest, LeaveType, StaffAttendance, StaffMember, Teacher
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

    def test_employee_self_service_includes_all_staff_profiles_in_the_school(self):
        first = StaffMember.objects.create(
            school=self.school,
            user=self.user,
            employee_number="STF-SELF-01",
            job_title="مشرف",
            role=StaffMember.StaffRole.SUPERVISOR,
        )
        second = StaffMember.objects.create(
            school=self.school,
            user=self.user,
            employee_number="STF-SELF-02",
            job_title="سكرتير",
            role=StaffMember.StaffRole.SECRETARY,
        )
        leave_type = LeaveType.objects.create(
            school=self.school,
            code="STAGE9-SELF",
            name="إجازة اختبار",
            days_allowed=10,
        )
        leave_one = LeaveRequest.objects.create(
            school=self.school, staff_member=first, leave_type=leave_type,
            start_date=date(2026, 11, 10), end_date=date(2026, 11, 10),
            reason="موعد",
        )
        leave_two = LeaveRequest.objects.create(
            school=self.school, staff_member=second, leave_type=leave_type,
            start_date=date(2026, 11, 12), end_date=date(2026, 11, 12),
            reason="مراجعة",
        )
        attendance_one = StaffAttendance.objects.create(
            school=self.school, staff_member=first, date=date(2026, 11, 10),
        )
        attendance_two = StaffAttendance.objects.create(
            school=self.school, staff_member=second, date=date(2026, 11, 12),
        )

        token, _ = Token.objects.get_or_create(user=self.user)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.key}",
            HTTP_X_SCHOOL_ID=str(self.school.pk),
        )

        leaves = client.get("/api/v1/staff/leaves/")
        attendance = client.get("/api/v1/staff/attendance/")
        self.assertEqual(leaves.status_code, 200)
        self.assertEqual(attendance.status_code, 200)
        self.assertEqual(
            {item["id"] for item in leaves.data},
            {str(leave_one.pk), str(leave_two.pk)},
        )
        self.assertEqual(
            {item["id"] for item in attendance.data},
            {str(attendance_one.pk), str(attendance_two.pk)},
        )

    def test_inactive_employee_cannot_submit_a_leave_request(self):
        inactive = StaffMember.objects.create(
            school=self.school,
            user=self.user,
            employee_number="STF-SELF-INACTIVE",
            job_title="موظف سابق",
            role=StaffMember.StaffRole.OTHER,
            is_active=False,
        )
        leave_type = LeaveType.objects.create(
            school=self.school,
            code="STAGE9-INACTIVE",
            name="إجازة",
            days_allowed=10,
        )
        token, _ = Token.objects.get_or_create(user=self.user)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.key}",
            HTTP_X_SCHOOL_ID=str(self.school.pk),
        )
        response = client.post(
            "/api/v1/staff/leaves/",
            {
                "staff_member_id": str(inactive.pk),
                "leave_type_id": str(leave_type.pk),
                "start_date": "2026-11-15",
                "end_date": "2026-11-15",
                "reason": "طلب إجازة",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LeaveRequest.objects.filter(staff_member=inactive).count(), 0)

    def test_payroll_approval_does_not_grant_post_or_disbursement_access(self):
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        self.role.permissions.add(Permission.objects.get(
            content_type__app_label="payroll",
            codename="approve_payrollrun",
        ))
        run = PayrollRun.objects.create(
            school=self.school,
            name="مسير اختبار الصلاحيات",
            year=2026,
            month=11,
        )
        token, _ = Token.objects.get_or_create(user=self.user)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.key}",
            HTTP_X_SCHOOL_ID=str(self.school.pk),
        )

        # Approval permission reaches the business rule (empty payroll cannot be approved).
        approved = client.post(
            f"/api/v1/payroll/runs/{run.pk}/approve/", {}, format="json",
        )
        self.assertEqual(approved.status_code, 400)

        # Approval alone must not authorize ledger posting, payment, or reversal.
        posted = client.post(f"/api/v1/payroll/runs/{run.pk}/post/", {}, format="json")
        disbursed = client.post(
            f"/api/v1/payroll/runs/{run.pk}/disburse/", {}, format="json",
        )
        reversed_run = client.post(
            f"/api/v1/payroll/runs/{run.pk}/reverse/",
            {"reason": "اختبار صلاحيات"}, format="json",
        )
        self.assertEqual(posted.status_code, 403)
        self.assertEqual(disbursed.status_code, 403)
        self.assertEqual(reversed_run.status_code, 403)

    def test_payroll_admin_cannot_bypass_financial_workflow(self):
        from django.contrib import admin
        from django.test import RequestFactory

        from apps.payroll.models import EmployeeLoanAdvance, Payslip

        request = RequestFactory().get("/admin/")
        request.user = self.owner
        run = PayrollRun.objects.create(
            school=self.school,
            name="مسير للعرض فقط",
            year=2026,
            month=10,
        )
        run_admin = admin.site._registry[PayrollRun]
        payslip_admin = admin.site._registry[Payslip]
        loan_admin = admin.site._registry[EmployeeLoanAdvance]

        self.assertFalse(run_admin.has_add_permission(request))
        self.assertFalse(run_admin.has_delete_permission(request, run))
        self.assertTrue({
            "status", "total_basic", "total_allowances", "total_deductions",
            "total_net", "approved_by", "journal_entry",
        }.issubset(set(run_admin.get_readonly_fields(request, run))))

        self.assertFalse(payslip_admin.has_add_permission(request))
        self.assertFalse(payslip_admin.has_delete_permission(request))
        self.assertEqual(
            set(payslip_admin.get_readonly_fields(request)),
            {field.name for field in Payslip._meta.fields},
        )

        self.assertFalse(loan_admin.has_add_permission(request))
        self.assertFalse(loan_admin.has_delete_permission(request))
        self.assertEqual(
            set(loan_admin.get_readonly_fields(request)),
            {field.name for field in EmployeeLoanAdvance._meta.fields},
        )

    def test_payroll_post_and_reverse_endpoints_return_the_persisted_state(self):
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        self.role.permissions.add(
            Permission.objects.get(
                content_type__app_label="payroll", codename="post_payrollrun",
            ),
            Permission.objects.get(
                content_type__app_label="payroll", codename="reverse_payrollrun",
            ),
        )
        run = PayrollRun.objects.create(
            school=self.school,
            name="مسير اختبار تحديث الحالة",
            year=2026,
            month=9,
            status=PayrollRun.Status.APPROVED,
        )
        token, _ = Token.objects.get_or_create(user=self.user)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.key}",
            HTTP_X_SCHOOL_ID=str(self.school.pk),
        )

        def post_and_persist(*, payroll_run, user):
            PayrollRun.objects.filter(pk=payroll_run.pk).update(
                status=PayrollRun.Status.POSTED,
            )
            return SimpleNamespace(entry_number="JE-STAGE9-TEST")

        with patch(
            "apps.payroll.api.views.post_payroll_to_accounting",
            side_effect=post_and_persist,
        ):
            posted = client.post(
                f"/api/v1/payroll/runs/{run.pk}/post/", {}, format="json",
            )
        self.assertEqual(posted.status_code, 200)
        self.assertEqual(posted.data["status"], PayrollRun.Status.POSTED)

        def reverse_and_persist(*, payroll_run, reason, reversed_by):
            PayrollRun.objects.filter(pk=payroll_run.pk).update(
                status=PayrollRun.Status.DRAFT,
                journal_entry=None,
            )
            return PayrollRun.objects.get(pk=payroll_run.pk)

        with patch(
            "apps.payroll.api.views.reverse_payroll_run",
            side_effect=reverse_and_persist,
        ):
            reversed_response = client.post(
                f"/api/v1/payroll/runs/{run.pk}/reverse/",
                {"reason": "اختبار العكس"},
                format="json",
            )
        self.assertEqual(reversed_response.status_code, 200)
        self.assertEqual(reversed_response.data["status"], PayrollRun.Status.DRAFT)
