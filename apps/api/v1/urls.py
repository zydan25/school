"""Versioned mobile application API routes."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.v1.views import (
    AcceptInvitationAPIView,
    AcademicTermViewSet,
    AcademicYearViewSet,
    AccountViewSet,
    AssetCategoryViewSet,
    AssetDepreciationViewSet,
    AssessmentTypeViewSet,
    ClassroomViewSet,
    ClassScheduleViewSet,
    ConversationAttachmentDownloadAPIView,
    CostCenterViewSet,
    DailyLessonLogViewSet,
    DepartmentViewSet,
    EducationalStageViewSet,
    ExamCommitteeViewSet,
    ExamSeatingViewSet,
    ExamSubmissionViewSet,
    ExpenseCategoryViewSet,
    FiscalPeriodViewSet,
    FiscalYearViewSet,
    FixedAssetViewSet,
    GradeBookViewSet,
    GradeLevelViewSet,
    GuardianChildrenAPIView,
    GuardianRelationViewSet,
    HomeworkAttachmentDownloadAPIView,
    HomeworkSubmissionViewSet,
    HomeworkViewSet,
    InventoryItemViewSet,
    JournalEntryViewSet,
    LeaveTypeViewSet,
    MembershipRoleViewSet,
    MembershipViewSet,
    MyProfilesAPIView,
    MyWeeklyTimetableAPIView,
    NotificationPreferenceViewSet,
    OnlineExamViewSet,
    PeriodDefinitionViewSet,
    PaymentVoucherViewSet,
    PushDeviceViewSet,
    PurchaseOrderItemViewSet,
    PurchaseOrderViewSet,
    QuestionBankViewSet,
    ReceiptVoucherViewSet,
    SchoolBellScheduleViewSet,
    SchoolConversationViewSet,
    SchoolInvitationAPIView,
    SchoolRoleViewSet,
    SchoolWorkingDayViewSet,
    SchedulePeriodTemplateViewSet,
    SectionViewSet,
    StockMovementViewSet,
    SubjectViewSet,
    SupplierViewSet,
    TeacherAssignmentViewSet,
    TeacherViewSet,
    VendorInvoiceViewSet,
    WarehouseViewSet,
    WorkShiftViewSet,
)

router = DefaultRouter()
router.register("memberships", MembershipViewSet, basename="app-membership")
router.register("roles", SchoolRoleViewSet, basename="app-school-role")
router.register("membership-roles", MembershipRoleViewSet, basename="app-membership-role")
router.register("guardian-relations", GuardianRelationViewSet, basename="app-guardian-relation")

router.register("academic-years", AcademicYearViewSet, basename="app-academic-year")
router.register("academic-terms", AcademicTermViewSet, basename="app-academic-term")
router.register("stages", EducationalStageViewSet, basename="app-stage")
router.register("grades", GradeLevelViewSet, basename="app-grade")
router.register("classrooms", ClassroomViewSet, basename="app-classroom")
router.register("sections", SectionViewSet, basename="app-section")
router.register("subjects", SubjectViewSet, basename="app-subject")
router.register("period-definitions", PeriodDefinitionViewSet, basename="app-period-definition")
router.register("working-days", SchoolWorkingDayViewSet, basename="app-working-day")

router.register("teachers", TeacherViewSet, basename="app-teacher")
router.register("teacher-assignments", TeacherAssignmentViewSet, basename="app-teacher-assignment")
router.register("departments", DepartmentViewSet, basename="app-department")
router.register("work-shifts", WorkShiftViewSet, basename="app-work-shift")
router.register("leave-types", LeaveTypeViewSet, basename="app-leave-type")

router.register("homework", HomeworkViewSet, basename="app-homework")
router.register("homework-submissions", HomeworkSubmissionViewSet, basename="app-homework-submission")
router.register("assessment-types", AssessmentTypeViewSet, basename="app-assessment-type")
router.register("gradebook", GradeBookViewSet, basename="app-gradebook")
router.register("question-bank", QuestionBankViewSet, basename="app-question-bank")
router.register("online-exams", OnlineExamViewSet, basename="app-online-exam")
router.register("exam-submissions", ExamSubmissionViewSet, basename="app-exam-submission")
router.register("exam-committees", ExamCommitteeViewSet, basename="app-exam-committee")
router.register("exam-seatings", ExamSeatingViewSet, basename="app-exam-seating")

router.register("bell-schedules", SchoolBellScheduleViewSet, basename="app-bell-schedule")
router.register("period-templates", SchedulePeriodTemplateViewSet, basename="app-period-template")
router.register("class-schedules", ClassScheduleViewSet, basename="app-class-schedule")
router.register("lesson-logs", DailyLessonLogViewSet, basename="app-lesson-log")

router.register("fiscal-years", FiscalYearViewSet, basename="app-fiscal-year")
router.register("fiscal-periods", FiscalPeriodViewSet, basename="app-fiscal-period")
router.register("accounts", AccountViewSet, basename="app-account")
router.register("cost-centers", CostCenterViewSet, basename="app-cost-center")
router.register("expense-categories", ExpenseCategoryViewSet, basename="app-expense-category")
router.register("journal-entries", JournalEntryViewSet, basename="app-journal-entry")
router.register("payment-vouchers", PaymentVoucherViewSet, basename="app-payment-voucher")
router.register("receipt-vouchers", ReceiptVoucherViewSet, basename="app-receipt-voucher")

router.register("suppliers", SupplierViewSet, basename="app-supplier")
router.register("warehouses", WarehouseViewSet, basename="app-warehouse")
router.register("inventory-items", InventoryItemViewSet, basename="app-inventory-item")
router.register("stock-movements", StockMovementViewSet, basename="app-stock-movement")
router.register("purchase-orders", PurchaseOrderViewSet, basename="app-purchase-order")
router.register("purchase-order-items", PurchaseOrderItemViewSet, basename="app-purchase-order-item")
router.register("vendor-invoices", VendorInvoiceViewSet, basename="app-vendor-invoice")
router.register("asset-categories", AssetCategoryViewSet, basename="app-asset-category")
router.register("fixed-assets", FixedAssetViewSet, basename="app-fixed-asset")
router.register("asset-depreciations", AssetDepreciationViewSet, basename="app-asset-depreciation")

router.register("devices", PushDeviceViewSet, basename="app-push-device")
router.register("notification-preferences", NotificationPreferenceViewSet, basename="app-notification-preference")
router.register("conversations", SchoolConversationViewSet, basename="app-conversation")

urlpatterns = [
    path("account/profiles/", MyProfilesAPIView.as_view(), name="app-my-profiles"),
    path("account/invitations/", SchoolInvitationAPIView.as_view(), name="app-invitations"),
    path("account/invitations/accept/", AcceptInvitationAPIView.as_view(), name="app-invitation-accept"),
    path("account/invitations/<uuid:invitation_id>/revoke/", SchoolInvitationAPIView.as_view(), {"action": "revoke"}, name="app-invitation-revoke"),
    path("my/children/", GuardianChildrenAPIView.as_view(), name="app-my-children"),
    path("my/timetable/", MyWeeklyTimetableAPIView.as_view(), name="app-my-timetable"),
    path("homework-submissions/<uuid:submission_id>/attachment/", HomeworkAttachmentDownloadAPIView.as_view(), name="app-homework-attachment"),
    path("conversation-messages/<uuid:message_id>/attachment/", ConversationAttachmentDownloadAPIView.as_view(), name="app-conversation-attachment"),
    path("", include(router.urls)),
]
