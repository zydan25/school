"""REST API views for comprehensive school reporting and analytics."""
from __future__ import annotations

import datetime
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from apps.students.models import Student
from apps.academics.models import Section, Subject, AcademicTerm
from apps.reports.selectors.financial_reports import (
    get_student_statement_of_account,
    get_aging_receivables_report,
    get_daily_cash_register_report,
)
from apps.reports.selectors.academic_reports import (
    get_student_report_card,
    get_class_ranking_report,
    get_subject_grade_distribution,
)
from apps.reports.selectors.attendance_reports import (
    get_section_attendance_summary,
    get_chronic_absenteeism_report,
)
from apps.reports.selectors.hr_reports import (
    get_teacher_workload_report,
    get_payroll_summary_report,
)
from apps.accounting.services.financial_reports import (
    get_trial_balance,
    get_income_statement,
    get_balance_sheet,
)


class BaseSchoolReportView(APIView):
    """قاعدة مشتركة لعزل تقارير المدرسة والتحقق من الصلاحيات والاشتراك."""
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self, request):
        school = getattr(request, "school", None)
        if not school:
            membership = request.user.school_memberships.filter(status="active").select_related("school").first()
            if membership:
                school = membership.school
        if not school and (request.user.is_superuser or request.user.is_platform_admin):
            school_code = request.query_params.get("school_code") or request.headers.get("X-School-Code")
            if school_code:
                from apps.tenants.models import School
                school = School.objects.filter(code=school_code, is_archived=False).first()
            else:
                from apps.tenants.models import School
                school = School.objects.filter(status=School.Status.ACTIVE).first()
        return school

    def check_financial_access(self, request, school) -> bool:
        """التحقق من أن المستخدم يمتلك صلاحية مالية أو إدارية في المدرسة."""
        if request.user.is_superuser or request.user.is_platform_admin or request.user.is_staff:
            return True
        membership = request.user.school_memberships.filter(school=school, status="active").first()
        if not membership:
            return False
        # Check user roles
        role_codes = list(membership.roles.values_list("code", flat=True)) if hasattr(membership, "roles") else []
        allowed_roles = {"principal", "school_admin", "accountant", "cashier", "financial_manager", "general_manager"}
        return bool(set(role_codes) & allowed_roles)

    def check_hr_access(self, request, school) -> bool:
        """التحقق من صلاحية الموارد البشرية والرواتب."""
        if request.user.is_superuser or request.user.is_platform_admin or request.user.is_staff:
            return True
        membership = request.user.school_memberships.filter(school=school, status="active").first()
        if not membership:
            return False
        role_codes = list(membership.roles.values_list("code", flat=True)) if hasattr(membership, "roles") else []
        allowed_roles = {"principal", "school_admin", "hr_manager", "accountant", "general_manager"}
        return bool(set(role_codes) & allowed_roles)


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
            is_own_guardian = request.user.guardian_profiles.filter(school=school, students=student).exists() if hasattr(request.user, "guardian_profiles") else False
            if not (is_own_student or is_own_guardian):
                return Response({"error": "غير مصرح لك بالاطلاع على كشف حساب هذا الطالب."}, status=status.HTTP_403_FORBIDDEN)

        data = get_student_statement_of_account(student)
        return Response(data)


class AgingReceivablesAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_financial_access(request, school):
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

        if not self.check_financial_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على ميزان المراجعة المحاسبي."}, status=status.HTTP_403_FORBIDDEN)

        data = get_trial_balance(school)
        return Response(data)


class IncomeStatementAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_financial_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على قائمة الدخل والأرباح والخسائر."}, status=status.HTTP_403_FORBIDDEN)

        data = get_income_statement(school)
        return Response(data)


class BalanceSheetAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        if not self.check_financial_access(request, school):
            return Response({"error": "غير مصرح لك بالاطلاع على قائمة المركز المالي والميزانية العمومية."}, status=status.HTTP_403_FORBIDDEN)

        data = get_balance_sheet(school)
        return Response(data)


# -----------------------------------------------------------------------------
# Academic Reports Views
# -----------------------------------------------------------------------------

class StudentReportCardAPIView(BaseSchoolReportView):
    def get(self, request, student_id=None, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        student = get_object_or_404(Student, id=student_id, school=school)

        # التحقق من صلاحية الوصول لشهادة الطالب
        if not (request.user.is_staff or request.user.is_superuser):
            is_own_student = (student.user_id == request.user.id)
            is_own_guardian = request.user.guardian_profiles.filter(school=school, students=student).exists() if hasattr(request.user, "guardian_profiles") else False
            is_teacher = request.user.school_memberships.filter(school=school, status="active").exists()
            if not (is_own_student or is_own_guardian or is_teacher):
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
        data = get_section_attendance_summary(section)
        return Response(data)


class ChronicAbsenteeismAPIView(BaseSchoolReportView):
    def get(self, request, *args, **kwargs):
        school = self.get_school(request)
        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

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
