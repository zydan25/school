"""REST API views for comprehensive school reporting and analytics."""
from __future__ import annotations

import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicTerm, Section, Subject
from apps.accounting.services.financial_reports import (
    get_balance_sheet,
    get_general_ledger,
    get_income_statement,
    get_trial_balance,
)
from apps.reports.selectors.academic_reports import (
    get_class_ranking_report,
    get_student_report_card,
    get_subject_grade_distribution,
)
from apps.reports.selectors.attendance_reports import (
    get_chronic_absenteeism_report,
    get_section_attendance_summary,
)
from apps.reports.selectors.financial_reports import (
    get_aging_receivables_report,
    get_billing_ledger_reconciliation_report,
    get_daily_cash_register_report,
    get_student_statement_of_account,
)
from apps.reports.selectors.hr_reports import (
    get_payroll_summary_report,
    get_teacher_workload_report,
)
from apps.students.models import Student


class BaseSchoolReportView(APIView):
    """قاعدة مشتركة لعزل تقارير المدرسة والتحقق من الصلاحيات والاشتراك."""
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self, request):
        school = getattr(request, "school", None)
        if school:
            return school
        school_code = request.query_params.get("school_code") or request.headers.get("X-School-Code")
        school_id = request.query_params.get("school_id") or request.headers.get("X-School-ID")
        from apps.tenants.models import School
        if school_id:
            school = School.objects.filter(id=school_id, is_archived=False).first()
        elif school_code:
            school = School.objects.filter(code=school_code, is_archived=False).first()
        if not school:
            now = timezone.now()
            membership = request.user.school_memberships.filter(
                status="active"
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
            ).select_related("school").first()
            if membership:
                school = membership.school
        return school

    def check_financial_access(self, request, school) -> bool:
        """التحقق من أن المستخدم يمتلك صلاحية مالية أو إدارية أو تحصيل في المدرسة (تشمل الكاشير)."""
        if request.user.is_superuser or getattr(request.user, "is_platform_admin", False):
            return True
        now = timezone.now()
        membership = request.user.school_memberships.filter(
            school=school, status="active"
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).first()
        if not membership:
            return False
        role_codes = membership.get_role_codes()
        allowed_roles = {
            "school-director", "school_director", "accountant", "cashier",
            "principal", "school_admin", "financial_manager", "general_manager"
        }
        return bool(role_codes & allowed_roles)

    def check_general_ledger_access(self, request, school) -> bool:
        """التحقق من صلاحية الاطلاع على القوائم المالية العامة ودفتر الأستاذ (تستثني الكاشير)."""
        if request.user.is_superuser or getattr(request.user, "is_platform_admin", False):
            return True
        now = timezone.now()
        membership = request.user.school_memberships.filter(
            school=school, status="active"
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).first()
        if not membership:
            return False
        role_codes = membership.get_role_codes()
        allowed_roles = {
            "school-director", "school_director", "accountant",
            "principal", "school_admin", "financial_manager", "general_manager"
        }
        return bool(role_codes & allowed_roles)

    def check_hr_access(self, request, school) -> bool:
        """التحقق من صلاحية الموارد البشرية والرواتب."""
        if request.user.is_superuser or getattr(request.user, "is_platform_admin", False):
            return True
        now = timezone.now()
        membership = request.user.school_memberships.filter(
            school=school, status="active"
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).first()
        if not membership:
            return False
        role_codes = membership.get_role_codes()
        allowed_roles = {
            "school-director", "school_director", "principal", "hr_manager",
            "hr-manager", "accountant", "general_manager"
        }
        return bool(role_codes & allowed_roles)

    def check_academic_access(self, request, school, section=None, subject=None) -> bool:
        """التحقق من صلاحية الوصول للتقارير الأكاديمية والدرجات."""
        if request.user.is_superuser or getattr(request.user, "is_platform_admin", False):
            return True
        now = timezone.now()
        membership = request.user.school_memberships.filter(
            school=school, status="active"
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).first()
        if not membership:
            return False
        role_codes = membership.get_role_codes()
        mgmt_roles = {
            "school-director", "school_director", "principal", "academic-coordinator",
            "academic_coordinator", "student-affairs", "control-officer", "general_manager"
        }
        if role_codes & mgmt_roles:
            return True

        if hasattr(request.user, "teacher_profiles"):
            teacher = request.user.teacher_profiles.filter(school=school).first()
            if teacher:
                assignments = teacher.assignments.filter(academic_year__status="active")
                if section and assignments.filter(section=section).exists():
                    return True
                if subject and assignments.filter(subject=subject).exists():
                    return True
                if not section and not subject:
                    return False
        return False


# -----------------------------------------------------------------------------
# Financial Reports Views
# -----------------------------------------------------------------------------

class StudentStatementOfAccountAPIView(BaseSchoolReportView):
    def get(self, request, student_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        student = get_object_or_404(Student, id=student_id, school=school)

        # التحقق من صلاحية الوصول لملف الطالب المالي
        if not self.check_financial_access(request, school):
            is_own_student = (student.user_id == request.user.id)
            is_own_guardian = request.user.guardian_profiles.filter(school=school, children=student).exists() if hasattr(request.user, "guardian_profiles") else False
            if not (is_own_student or is_own_guardian):
                return Response({"error": "غير مصرح لك بالاطلاع على كشف حساب هذا الطالب."}, status=status.HTTP_403_FORBIDDEN)

        data = get_student_statement_of_account(student)
        return Response(data)


class AgingReceivablesAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_general_ledger_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على تقرير أعمار الديون والذمم المالية."}, status=status.HTTP_403_FORBIDDEN)

        data = get_aging_receivables_report(school)
        return Response(data)


class DailyCashRegisterAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_financial_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على حركة الصندوق والمقبوضات اليومية."}, status=status.HTTP_403_FORBIDDEN)

        date_str = request.query_params.get("date")
        target_date = None
        if date_str:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return Response({"error": "تنسيق التاريخ غير صحيح. يجب أن يكون YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        data = get_daily_cash_register_report(school, target_date=target_date)
        return Response(data)


class TrialBalanceAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_general_ledger_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على ميزان المراجعة المحاسبي."}, status=status.HTTP_403_FORBIDDEN)

        data = get_trial_balance(school)
        return Response(data)


class IncomeStatementAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_general_ledger_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على قائمة الدخل والأرباح والخسائر."}, status=status.HTTP_403_FORBIDDEN)

        data = get_income_statement(school)
        return Response(data)


class BalanceSheetAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_general_ledger_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على قائمة المركز المالي والميزانية العمومية."}, status=status.HTTP_403_FORBIDDEN)

        data = get_balance_sheet(school)
        return Response(data)


class BillingLedgerReconciliationAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_general_ledger_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على تقرير مطابقة الفواتير ودفتر الأستاذ."}, status=status.HTTP_403_FORBIDDEN)

        data = get_billing_ledger_reconciliation_report(school)
        return Response(data)


# -----------------------------------------------------------------------------
class GeneralLedgerAPIView(BaseSchoolReportView):
    """كشف حركة حساب تفصيلي للمحاسب والإدارة المخولة."""
    def get(self, request, account_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)
        if not self.check_general_ledger_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على دفتر الأستاذ العام."}, status=status.HTTP_403_FORBIDDEN)

        from apps.accounting.models import Account

        account = get_object_or_404(
            Account,
            pk=account_id,
            school=school,
            is_archived=False,
        )
        start_value = request.query_params.get("start_date")
        end_value = request.query_params.get("end_date")
        try:
            start_date = datetime.date.fromisoformat(start_value) if start_value else None
            end_date = datetime.date.fromisoformat(end_value) if end_value else None
            data = get_general_ledger(account, start_date=start_date, end_date=end_date)
        except (ValueError, ValidationError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)


# Academic Reports Views
# -----------------------------------------------------------------------------

class StudentReportCardAPIView(BaseSchoolReportView):
    def get(self, request, student_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        student = get_object_or_404(Student, id=student_id, school=school)

        # التحقق الصارم من صلاحية الوصول لشهادة الطالب ومنع تجاوز is_staff
        from apps.accounts.services import is_platform_operator
        from django.db.models import Q
        if not is_platform_operator(request.user):
            now = timezone.now()
            membership = request.user.school_memberships.filter(
                school=school,
                status="active",
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            ).first()

            is_own_student = (student.user_id == request.user.id)
            is_own_guardian = request.user.guardian_profiles.filter(school=school, children=student).exists() if hasattr(request.user, "guardian_profiles") else False
            
            # المعلم أو المشرف الأكاديمي المصرح له
            user_roles = membership.get_role_codes() if membership else set()
            is_academic = bool(user_roles & {"school-director", "school_director", "academic-coordinator", "academic_coordinator", "student-affairs", "control-officer"})
            is_section_teacher = False
            if hasattr(request.user, "teacher_profiles"):
                teacher = request.user.teacher_profiles.filter(school=school).first()
                if teacher:
                    is_section_teacher = teacher.assignments.filter(section=student.section).exists()

            if not (is_own_student or is_own_guardian or is_academic or is_section_teacher):
                return Response({"error": "غير مصرح لك بالاطلاع على درجات هذا الطالب."}, status=status.HTTP_403_FORBIDDEN)

        term_id = request.query_params.get("term_id")
        term = None
        if term_id:
            term = get_object_or_404(AcademicTerm, id=term_id, academic_year__school=school)

        data = get_student_report_card(student, term=term)
        return Response(data)


class ClassRankingAPIView(BaseSchoolReportView):
    def get(self, request, section_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        section = get_object_or_404(Section, id=section_id, school=school)
        if not self.check_academic_access(request, school, section=section):
            return Response({"error": "غير مصرح لك بالاطلاع على تقرير ترتيب هذه الشعبة."}, status=status.HTTP_403_FORBIDDEN)

        term_id = request.query_params.get("term_id")
        term = None
        if term_id:
            term = get_object_or_404(AcademicTerm, id=term_id, academic_year__school=school)

        data = get_class_ranking_report(section, term=term)
        return Response(data)


class SubjectGradeDistributionAPIView(BaseSchoolReportView):
    def get(self, request, subject_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        subject = get_object_or_404(Subject, id=subject_id, school=school)
        if not self.check_academic_access(request, school, subject=subject):
            return Response({"error": "غير مصرح لك بالاطلاع على توزيع درجات هذه المادة."}, status=status.HTTP_403_FORBIDDEN)

        term_id = request.query_params.get("term_id")
        term = None
        if term_id:
            term = get_object_or_404(AcademicTerm, id=term_id, academic_year__school=school)

        data = get_subject_grade_distribution(subject, term=term)
        return Response(data)


# -----------------------------------------------------------------------------
# Attendance Reports Views
# -----------------------------------------------------------------------------

class SectionAttendanceSummaryAPIView(BaseSchoolReportView):
    def get(self, request, section_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        section = get_object_or_404(Section, id=section_id, school=school)
        if not self.check_academic_access(request, school, section=section):
            return Response({"error": "غير مصرح لك بالاطلاع على تقرير حضور هذه الشعبة."}, status=status.HTTP_403_FORBIDDEN)

        data = get_section_attendance_summary(section)
        return Response(data)


class ChronicAbsenteeismAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_academic_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على تقرير الغياب المزمن."}, status=status.HTTP_403_FORBIDDEN)

        threshold = int(request.query_params.get("threshold", 5))
        data = get_chronic_absenteeism_report(school, threshold=threshold)
        return Response(data)


# -----------------------------------------------------------------------------
# HR & Workload Reports Views
# -----------------------------------------------------------------------------

class TeacherWorkloadAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not (self.check_hr_access(request, school) or self.check_academic_access(request, school)):
            return Response({"error": "غير مصرح لك بالاطلاع على تقرير نصاب المعلمين."}, status=status.HTTP_403_FORBIDDEN)

        data = get_teacher_workload_report(school)
        return Response(data)


class PayrollSummaryAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_hr_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على مسير ورواتب الموظفين."}, status=status.HTTP_403_FORBIDDEN)

        year = int(request.query_params.get("year", datetime.date.today().year))
        month = int(request.query_params.get("month", datetime.date.today().month))

        data = get_payroll_summary_report(school, year=year, month=month)
        return Response(data)
