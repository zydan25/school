from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.assessments.models import (
    AssessmentType,
    ExamCommittee,
    ExamCommitteeProctor,
    ExamSeating,
    GradeBook,
    OnlineExam,
    QuestionBank,
    StudentOnlineExamSubmission,
)
from apps.auditlog.services import record_event
from apps.assessments.models import GradeBook as GradeBookModel
from django.utils import timezone
from apps.core.admin import AuditedAdminMixin


@admin.register(AssessmentType)
class AssessmentTypeAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "weight_percentage", "default_max_score", "school")
    list_filter = ("school",)
    search_fields = ("name", "code", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(GradeBook)
class GradeBookAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "subject", "assessment_title", "score", "max_score", "workflow_status", "is_published", "graded_by", "graded_at", "school")
    list_filter = ("workflow_status", "is_published", "subject", "academic_term", "school")
    actions = ("approve_selected", "publish_selected")
    search_fields = ("student__first_name", "student__last_name", "assessment_title", "subject__name", "school__name")
    autocomplete_fields = ("school", "branch", "student", "subject", "academic_term", "assessment_type", "homework", "graded_by")
    readonly_fields = (
        "id", "created_at", "updated_at", "workflow_status", "is_published",
        "submitted_by", "submitted_at", "approved_by", "approved_at",
        "published_by", "published_at", "revision_reason",
    )

    @admin.action(description="اعتماد الدرجات المرسلة للمراجعة")
    def approve_selected(self, request, queryset):
        updated = 0
        for entry in queryset.filter(workflow_status=GradeBookModel.WorkflowStatus.SUBMITTED):
            entry.workflow_status = GradeBookModel.WorkflowStatus.APPROVED
            entry.approved_by = request.user
            entry.approved_at = timezone.now()
            entry.save(update_fields=["workflow_status", "approved_by", "approved_at", "updated_at"])
            record_event(
                action="gradebook.approved",
                description="تم اعتماد الدرجة من لوحة الإدارة.",
                actor=request.user, school=entry.school, obj=entry, request=request,
            )
            updated += 1
        self.message_user(request, f"تم اعتماد {updated} درجة.")

    @admin.action(description="نشر الدرجات المعتمدة")
    def publish_selected(self, request, queryset):
        updated = 0
        for entry in queryset.filter(workflow_status=GradeBookModel.WorkflowStatus.APPROVED):
            entry.workflow_status = GradeBookModel.WorkflowStatus.PUBLISHED
            entry.is_published = True
            entry.published_by = request.user
            entry.published_at = timezone.now()
            entry.save(update_fields=[
                "workflow_status", "is_published", "published_by", "published_at", "updated_at",
            ])
            record_event(
                action="gradebook.published",
                description="تم نشر الدرجة من لوحة الإدارة بعد اعتمادها.",
                actor=request.user, school=entry.school, obj=entry, request=request,
            )
            updated += 1
        self.message_user(request, f"تم نشر {updated} درجة معتمدة.")


class ExamCommitteeProctorInline(admin.TabularInline):
    model = ExamCommitteeProctor
    extra = 0
    autocomplete_fields = ("teacher",)
    readonly_fields = ("assigned_by", "assigned_at")


@admin.register(ExamCommittee)
class ExamCommitteeAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("committee_number", "name", "location_room", "capacity", "head_supervisor", "school")
    list_filter = ("school",)
    search_fields = ("committee_number", "name", "location_room")
    raw_id_fields = ("head_supervisor", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (ExamCommitteeProctorInline,)


@admin.register(ExamSeating)
class ExamSeatingAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("seating_number", "student", "committee", "academic_year", "secret_code", "school")
    list_filter = ("school", "academic_year", "committee")
    search_fields = ("seating_number", "secret_code", "student__first_name", "student__last_name")
    raw_id_fields = ("student", "committee", "academic_year", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(QuestionBank)
class QuestionBankAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("question_text_short", "subject", "grade_level", "unit_name", "question_type", "difficulty", "default_marks", "created_by", "school")
    list_filter = ("question_type", "difficulty", "subject", "grade_level", "school")
    search_fields = ("question_text", "unit_name", "topic", "subject__name")
    raw_id_fields = ("subject", "grade_level", "created_by", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")

    def question_text_short(self, obj):
        return obj.question_text[:50] + ("..." if len(obj.question_text) > 50 else "")
    question_text_short.short_description = "نص السؤال"


@admin.register(OnlineExam)
class OnlineExamAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "subject", "academic_term", "grade_level", "exam_type", "duration_minutes", "total_marks", "passing_marks", "is_published", "created_by", "school")
    list_filter = ("is_published", "exam_type", "subject", "school")
    search_fields = ("title", "subject__name", "instructions")
    raw_id_fields = ("subject", "academic_term", "grade_level", "section", "created_by", "school", "branch")
    filter_horizontal = ("questions",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentOnlineExamSubmission)
class StudentOnlineExamSubmissionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("exam", "student", "final_score", "auto_score", "status", "submitted_at", "school")
    list_filter = ("status", "exam", "school")
    search_fields = ("student__first_name", "student__last_name", "exam__title")
    raw_id_fields = ("exam", "student", "graded_by", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "submitted_at")


@admin.register(ExamCommitteeProctor)
class ExamCommitteeProctorAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("committee", "teacher", "duty", "assigned_at", "school")
    list_filter = ("duty", "school")
    search_fields = ("committee__name", "teacher__user__first_name", "teacher__user__last_name")
    autocomplete_fields = ("school", "branch", "committee", "teacher")
    readonly_fields = ("id", "created_at", "updated_at", "assigned_by", "assigned_at")
