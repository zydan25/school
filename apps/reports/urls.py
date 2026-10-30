"""URLs routing for reports and analytics."""
from django.urls import path

from apps.reports.views import (
    StudentStatementOfAccountAPIView,
    AgingReceivablesAPIView,
    DailyCashRegisterAPIView,
    TrialBalanceAPIView,
    IncomeStatementAPIView,
    BalanceSheetAPIView,
    StudentReportCardAPIView,
    ClassRankingAPIView,
    SubjectGradeDistributionAPIView,
    SectionAttendanceSummaryAPIView,
    ChronicAbsenteeismAPIView,
    TeacherWorkloadAPIView,
    PayrollSummaryAPIView,
)

app_name = "reports"

urlpatterns = [
    # Financial Reports
    path("financial/student-statement/<uuid:student_id>/", StudentStatementOfAccountAPIView.as_view(), name="student-statement"),
    path("financial/aging-receivables/", AgingReceivablesAPIView.as_view(), name="aging-receivables"),
    path("financial/daily-cash/", DailyCashRegisterAPIView.as_view(), name="daily-cash"),
    path("financial/trial-balance/", TrialBalanceAPIView.as_view(), name="trial-balance"),
    path("financial/income-statement/", IncomeStatementAPIView.as_view(), name="income-statement"),
    path("financial/balance-sheet/", BalanceSheetAPIView.as_view(), name="balance-sheet"),

    # Academic Reports
    path("academic/report-card/<uuid:student_id>/", StudentReportCardAPIView.as_view(), name="report-card"),
    path("academic/class-ranking/<uuid:section_id>/", ClassRankingAPIView.as_view(), name="class-ranking"),
    path("academic/subject-distribution/<uuid:subject_id>/", SubjectGradeDistributionAPIView.as_view(), name="subject-distribution"),

    # Attendance Reports
    path("attendance/section-summary/<uuid:section_id>/", SectionAttendanceSummaryAPIView.as_view(), name="section-attendance-summary"),
    path("attendance/chronic-absenteeism/", ChronicAbsenteeismAPIView.as_view(), name="chronic-absenteeism"),

    # HR & Payroll Reports
    path("hr/teacher-workload/", TeacherWorkloadAPIView.as_view(), name="teacher-workload"),
    path("hr/payroll-summary/", PayrollSummaryAPIView.as_view(), name="payroll-summary"),
]
