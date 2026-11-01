from django.contrib import admin
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils import timezone
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

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.workflow_status != GradeBook.WorkflowStatus.DRAFT:
            fields.extend([
                "student", "subject", "academic_term", "assessment_type",
                "homework", "assessment_title", "score", "max_score",
                "teacher_feedback", "graded_by", "graded_at",
            ])
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.workflow_status != GradeBook.WorkflowStatus.DRAFT:
            return False
        return super().has_delete_permission(request, obj)

    @admin.action(description="اعتماد الدرجات المرسلة للمراجعة")
    def approve_selected(self, request, queryset):
        updated = 0
        for entry in queryset.filter(workflow_status=GradeBook.WorkflowStatus.SUBMITTED):
            entry.workflow_status = GradeBook.WorkflowStatus.APPROVED
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
        for entry in queryset.filter(workflow_status=GradeBook.WorkflowStatus.APPROVED):
            entry.workflow_status = GradeBook.WorkflowStatus.PUBLISHED
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
    can_delete = False
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

    def has_delete_permission(self, request, obj=None):
        if obj and obj.seatings.filter(is_archived=False).exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ExamSeating)
class ExamSeatingAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("seating_number", "student", "committee", "academic_year", "secret_code", "school")
    list_filter = ("school", "academic_year", "committee")
    search_fields = ("seating_number", "secret_code", "student__first_name", "student__last_name")
    raw_id_fields = ("student", "committee", "academic_year", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


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

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.included_in_exams.filter(
            models.Q(is_published=True) | models.Q(submissions__is_archived=False),
            is_archived=False,
        ).distinct().exists():
            fields.extend([
                "subject", "grade_level", "unit_name", "topic", "question_text",
                "question_type", "difficulty", "default_marks", "options_json",
                "correct_answer", "model_answer_explanation",
            ])
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.included_in_exams.exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(OnlineExam)
class OnlineExamAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "subject", "academic_term", "grade_level", "exam_type", "duration_minutes", "total_marks", "passing_marks", "is_published", "created_by", "school")
    list_filter = ("is_published", "exam_type", "subject", "school")
    search_fields = ("title", "subject__name", "instructions")
    raw_id_fields = ("subject", "academic_term", "grade_level", "section", "created_by", "school", "branch")
    filter_horizontal = ("questions",)
    actions = ("publish_selected",)
    readonly_fields = (
        "id", "created_at", "updated_at", "is_published",
        "published_by", "published_at", "unpublished_reason",
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.submissions.filter(is_archived=False).exists():
            fields.extend([
                "title", "subject", "academic_term", "grade_level", "section",
                "exam_type", "duration_minutes", "total_marks", "passing_marks",
                "start_time", "end_time", "instructions", "questions",
            ])
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.submissions.filter(is_archived=False).exists():
            return False
        return super().has_delete_permission(request, obj)

    @admin.action(description="نشر الاختبارات المكتملة")
    def publish_selected(self, request, queryset):
        published = 0
        for exam in queryset.filter(is_published=False):
            questions = list(exam.questions.all())
            if not questions:
                continue
            if any(question.school_id != exam.school_id or question.subject_id != exam.subject_id for question in questions):
                continue
            if sum((question.default_marks for question in questions), Decimal("0.00")) > exam.total_marks:
                continue
            try:
                exam.full_clean()
            except ValidationError:
                continue
            exam.is_published = True
            exam.published_by = request.user
            exam.published_at = timezone.now()
            exam.unpublished_reason = ""
            exam.save(update_fields=[
                "is_published", "published_by", "published_at",
                "unpublished_reason", "updated_at",
            ])
            record_event(
                action="assessment.exam_published",
                description="تم نشر الاختبار من لوحة الإدارة.",
                actor=request.user, school=exam.school, obj=exam, request=request,
            )
            published += 1
        self.message_user(request, f"تم نشر {published} اختباراً.")


@admin.register(StudentOnlineExamSubmission)
class StudentOnlineExamSubmissionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("exam", "student", "final_score", "auto_score", "status", "submitted_at", "school")
    list_filter = ("status", "result_published", "exam", "school")
    search_fields = ("student__first_name", "student__last_name", "exam__title")
    raw_id_fields = ("exam", "student", "graded_by", "school", "branch", "result_published_by")
    actions = ("publish_results",)
    readonly_fields = (
        "id", "created_at", "updated_at", "started_at", "submitted_at",
        "exam", "student", "answers_json", "auto_score", "manual_score",
        "final_score", "teacher_feedback", "status", "graded_by",
        "result_published", "result_published_at", "result_published_by",
        "result_revision_reason",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="نشر نتائج المحاولات المصححة")
    def publish_results(self, request, queryset):
        published = 0
        for submission in queryset.filter(
            status=StudentOnlineExamSubmission.Status.GRADED,
            result_published=False,
        ):
            submission.result_published = True
            submission.result_published_at = timezone.now()
            submission.result_published_by = request.user
            submission.result_revision_reason = ""
            submission.save(update_fields=[
                "result_published", "result_published_at",
                "result_published_by", "result_revision_reason", "updated_at",
            ])
            record_event(
                action="assessment.exam_result_published",
                description="تم نشر نتيجة الاختبار من لوحة الإدارة.",
                actor=request.user, school=submission.school,
                obj=submission, request=request,
            )
            published += 1
        self.message_user(request, f"تم نشر {published} نتيجة.")


@admin.register(ExamCommitteeProctor)
class ExamCommitteeProctorAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("committee", "teacher", "duty", "assigned_at", "school")
    list_filter = ("duty", "school")
    search_fields = ("committee__name", "teacher__user__first_name", "teacher__user__last_name")
    autocomplete_fields = ("school", "branch", "committee", "teacher")
    readonly_fields = ("id", "created_at", "updated_at", "assigned_by", "assigned_at")

    def has_delete_permission(self, request, obj=None):
        return False
