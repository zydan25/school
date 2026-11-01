"""Serializers for the mobile/web REST surface. All tenant FKs are checked here."""
from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import (
    MembershipRole, SchoolInvitation, SchoolMembership, SchoolRole, User,
)
from apps.accounts.services import school_assignable_permissions
from apps.academics.models import (
    AcademicTerm, AcademicYear, Classroom, EducationalStage, GradeLevel,
    PeriodDefinition, SchoolWorkingDay, Section, Subject,
)
from apps.accounting.models import (
    Account, CostCenter, ExpenseCategory, FiscalPeriod, FiscalYear,
    JournalEntry, JournalEntryLine, PaymentVoucher, ReceiptVoucher,
)
from apps.assets.models import AssetCategory, AssetDepreciationEntry, FixedAsset
from apps.assessments.models import (
    AssessmentType, ExamCommittee, ExamCommitteeProctor, ExamSeating, GradeBook, OnlineExam,
    QuestionBank, StudentOnlineExamSubmission,
)
from apps.assignments.models import Homework, HomeworkSubmission, HomeworkSubmissionAttempt
from apps.inventory.models import (
    InventoryItem, PurchaseOrder, PurchaseOrderItem, StockMovement,
    Supplier, VendorInvoice, Warehouse,
)
from apps.notifications.models import (
    ConversationMessage, ConversationParticipant,
    NotificationPreference, PushDevice, SchoolConversation,
)
from apps.staff.models import (
    Department, LeaveRequest, LeaveType, StaffMember,
    Teacher, TeacherAssignment, WorkShift,
)
from apps.students.models import (
    Guardian, Student, StudentEnrollment, StudentGuardianRelation,
)
from apps.timetable.models import (
    ClassSchedule, DailyLessonLog, SchedulePeriodTemplate, SchoolBellSchedule, TimetablePlan,
)
from apps.tenants.models import Branch


class TenantModelSerializer(serializers.ModelSerializer):
    """Reject cross-school related objects and never accept the tenant from the client."""

    class Meta:
        fields = "__all__"
        read_only_fields = (
            "id", "school", "branch", "created_at", "updated_at",
            "is_archived", "archived_at", "archived_by",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        if school:
            model = getattr(self.Meta, "model", None)
            for model_field in model._meta.fields if model else ():
                if not getattr(model_field, "many_to_one", False):
                    continue
                name = model_field.name
                related = attrs.get(name)
                if related is None and self.instance is not None:
                    related = getattr(self.instance, name, None)
                related_school_id = getattr(related, "school_id", None) if related else None
                if related_school_id is not None and str(related_school_id) != str(school.pk):
                    raise serializers.ValidationError({name: "العنصر المرتبط لا يتبع المدرسة النشطة."})

            # Many-to-many relations (notably OnlineExam.questions) need the same
            # tenant check; DRF resolves them after validate(), so inspect input.
            for model_field in model._meta.many_to_many if model else ():
                name = model_field.name
                related_items = attrs.get(name)
                if related_items is None:
                    continue
                for related in related_items:
                    related_school_id = getattr(related, "school_id", None)
                    if related_school_id is not None and str(related_school_id) != str(school.pk):
                        raise serializers.ValidationError({name: "يحتوي الحقل على عنصر تابع لمدرسة أخرى."})

            if self.instance and str(self.instance.school_id) != str(school.pk):
                raise serializers.ValidationError("لا يمكن نقل سجل بين المدارس من خلال API.")
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "phone", "email", "first_name", "middle_name", "last_name",
            "full_name", "preferred_language", "timezone", "avatar",
            "phone_verified_at", "email_verified_at", "last_seen_at",
        ]
        read_only_fields = [
            "id", "phone", "full_name", "phone_verified_at",
            "email_verified_at", "last_seen_at",
        ]


class MembershipSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(read_only=True)
    school_code = serializers.CharField(source="school.code", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    role_codes = serializers.SerializerMethodField()

    class Meta:
        model = SchoolMembership
        fields = [
            "id", "school_id", "school_code", "school_name", "user",
            "user_name", "user_phone", "status", "is_default", "joined_at",
            "expires_at", "notes", "role_codes",
        ]
        read_only_fields = ["id", "school_id", "school_code", "school_name", "user_name", "user_phone", "role_codes", "joined_at"]

    def get_role_codes(self, obj):
        return sorted(obj.get_role_codes())


class SchoolRoleSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = school_assignable_permissions()

    class Meta:
        model = SchoolRole
        fields = [
            "id", "code", "name", "description", "permissions",
            "is_system", "is_active", "is_archived",
        ]
        read_only_fields = ["id", "is_system", "is_archived"]


class MembershipRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)

    class Meta:
        model = MembershipRole
        fields = ["id", "membership", "role", "role_name", "role_code", "valid_from", "valid_until"]
        read_only_fields = ["id", "role_name", "role_code"]


class InvitationSerializer(serializers.ModelSerializer):
    role_names = serializers.SerializerMethodField()
    invited_by_name = serializers.CharField(source="invited_by.get_full_name", read_only=True)

    class Meta:
        model = SchoolInvitation
        fields = [
            "id", "email", "phone", "status", "expires_at",
            "invited_by_name", "accepted_by", "accepted_at", "roles",
            "role_names", "message", "created_at",
        ]
        read_only_fields = ["id", "status", "invited_by_name", "accepted_by", "accepted_at", "role_names", "created_at"]

    def get_role_names(self, obj):
        return [{"id": str(role.pk), "code": role.code, "name": role.name} for role in obj.roles.all()]


class StudentSerializer(TenantModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    grade_name = serializers.CharField(source="grade_level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = Student
        fields = [
            "id", "student_id_number", "first_name", "middle_name", "last_name",
            "full_name", "national_id", "birth_date", "gender", "grade_level",
            "grade_name", "section", "section_name", "academic_year",
            "academic_year_name", "enrollment_date", "status", "credit_balance",
        ]
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("credit_balance",)


class StudentEnrollmentSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = StudentEnrollment
        fields = "__all__"


class GuardianSerializer(TenantModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = Guardian
        fields = [
            "id", "user", "full_name", "phone", "national_id",
            "relationship_type", "occupation", "emergency_phone",
        ]
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("user",)


class StudentGuardianRelationSerializer(TenantModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    guardian_name = serializers.CharField(source="guardian.user.get_full_name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = StudentGuardianRelation
        fields = [
            "id", "student", "student_name", "guardian", "guardian_name",
            "is_primary", "receives_notifications", "can_pickup",
        ]


class BranchSerializer(serializers.ModelSerializer):
    """Branch management contract; school ownership is supplied by the server."""

    class Meta:
        model = Branch
        fields = "__all__"
        read_only_fields = (
            "id", "school", "created_at", "updated_at", "is_archived",
            "archived_at", "archived_by",
        )
        validators = []  # School-scoped uniqueness is validated with the server-supplied school.

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        code = (attrs.get("code") or getattr(self.instance, "code", "")).strip().upper()
        if school and code:
            duplicates = Branch.objects.filter(school=school, code=code)
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError({"code": "كود الفرع مستخدم بالفعل في المدرسة."})
        is_main = attrs.get("is_main", getattr(self.instance, "is_main", False))
        if school and is_main:
            main_branches = Branch.objects.filter(school=school, is_main=True, is_archived=False)
            if self.instance:
                main_branches = main_branches.exclude(pk=self.instance.pk)
            if main_branches.exists():
                raise serializers.ValidationError({"is_main": "يوجد فرع رئيسي نشط بالفعل لهذه المدرسة."})
        if code:
            attrs["code"] = code
        return attrs


class AcademicStructureBranchMixin:
    """Mixin for allowing a school-owned branch on academic serializers only."""

    def get_fields(self):
        fields = super().get_fields()
        if "branch" in fields:
            school = self.context.get("school")
            fields["branch"].queryset = (
                Branch.objects.filter(school=school, is_archived=False)
                if school else Branch.objects.none()
            )
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        model = getattr(self.Meta, "model", None)
        related_branch_ids = set()
        if model:
            for model_field in model._meta.fields:
                if not getattr(model_field, "many_to_one", False):
                    continue
                field_name = model_field.name
                if field_name in {"school", "branch"}:
                    continue
                related = attrs.get(field_name)
                if related is None and self.instance is not None:
                    related = getattr(self.instance, field_name, None)
                related_branch_id = getattr(related, "branch_id", None) if related else None
                if related_branch_id:
                    related_branch_ids.add(related_branch_id)
        if len(related_branch_ids) > 1:
            raise serializers.ValidationError("العلاقات الأكاديمية المحددة تتبع فروعاً مختلفة.")

        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if related_branch_ids:
            required_branch_id = next(iter(related_branch_ids))
            if branch is None:
                branch = Branch.objects.filter(
                    pk=required_branch_id,
                    school=school,
                    is_archived=False,
                ).first()
                if branch is None:
                    raise serializers.ValidationError({"branch": "تعذر تحديد الفرع المرتبط بالبيانات الأكاديمية."})
                attrs["branch"] = branch
            elif branch.pk != required_branch_id:
                raise serializers.ValidationError({"branch": "الفرع المحدد لا يطابق فروع العناصر الأكاديمية المرتبطة."})
        if branch and school and (branch.school_id != school.pk or branch.is_archived):
            raise serializers.ValidationError({"branch": "الفرع غير نشط أو لا يتبع المدرسة الحالية."})
        return attrs


class AcademicYearSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = AcademicYear
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class AcademicTermSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = AcademicTerm
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class EducationalStageSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = EducationalStage
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class GradeLevelSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = GradeLevel
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class ClassroomSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = Classroom
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class SectionSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    student_count = serializers.IntegerField(source="current_student_count", read_only=True)
    available_seats = serializers.IntegerField(read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = Section
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch") + ("student_count", "available_seats")


class SubjectSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = Subject
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class PeriodDefinitionSerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = PeriodDefinition
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class SchoolWorkingDaySerializer(AcademicStructureBranchMixin, TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = SchoolWorkingDay
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch")


class TeacherSerializer(TenantModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = Teacher
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("user",)


class TeacherAssignmentSerializer(TenantModelSerializer):
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = TeacherAssignment
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("teacher_name", "subject_name", "section_name")


class StaffMemberSerializer(TenantModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = StaffMember
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("user",)


class DepartmentSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = Department
        fields = "__all__"


class WorkShiftSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = WorkShift
        fields = "__all__"


class LeaveTypeSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = LeaveType
        fields = "__all__"


class LeaveRequestDomainSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = LeaveRequest
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("status", "approved_by", "approved_at")


class HomeworkSerializer(TenantModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = Homework
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("teacher", "subject_name", "section_name", "teacher_name")


class HomeworkSubmissionAttemptSerializer(TenantModelSerializer):
    attachment_name = serializers.SerializerMethodField()

    class Meta(TenantModelSerializer.Meta):
        model = HomeworkSubmissionAttempt
        fields = [
            "id", "attempt_number", "submission_text", "attachment_name",
            "submitted_at", "status",
        ]
        read_only_fields = fields

    def get_attachment_name(self, obj):
        return obj.attachment.name.rsplit("/", 1)[-1] if obj.attachment else ""


class HomeworkSubmissionSerializer(TenantModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    attempts = HomeworkSubmissionAttemptSerializer(many=True, read_only=True)
    attachment = serializers.FileField(write_only=True, required=False)
    attachment_name = serializers.SerializerMethodField()
    attachment_available = serializers.SerializerMethodField()

    class Meta(TenantModelSerializer.Meta):
        model = HomeworkSubmission
        fields = [
            "id", "homework", "student", "student_name", "submission_text",
            "attachment", "attachment_name", "attachment_available",
            "submitted_at", "status", "score", "teacher_feedback", "graded_by", "graded_at",
            "attempts",
        ]
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "student", "student_name", "attachment_name", "attachment_available",
            "submitted_at", "status", "score", "teacher_feedback", "graded_by", "graded_at",
            "attempts",
        )

    def get_attachment_name(self, obj):
        return obj.attachment.name.rsplit("/", 1)[-1] if obj.attachment else ""

    def get_attachment_available(self, obj):
        return bool(obj.attachment and not obj.is_archived)


class AssessmentTypeSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = AssessmentType
        fields = "__all__"


class GradeBookSerializer(TenantModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    academic_term_name = serializers.CharField(source="academic_term.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = GradeBook
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "student_name", "subject_name", "academic_term_name", "graded_by", "graded_at",
            "workflow_status", "is_published", "submitted_by", "submitted_at",
            "approved_by", "approved_at", "published_by", "published_at", "revision_reason",
        )


class QuestionBankTeacherSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = QuestionBank
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("created_by",)


class ExamPaperQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionBank
        fields = ["id", "question_text", "question_type", "difficulty", "default_marks", "options_json", "unit_name", "topic"]


class OnlineExamSerializer(TenantModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = OnlineExam
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "created_by", "is_published", "published_by", "published_at",
            "unpublished_reason",
        )


class ExamSubmissionSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = StudentOnlineExamSubmission
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "student", "started_at", "submitted_at", "answers_json",
            "auto_score", "manual_score", "final_score", "status", "graded_by",
        )


class ExamSubmissionReviewSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)

    class Meta:
        model = StudentOnlineExamSubmission
        fields = "__all__"
        read_only_fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            from apps.accounts.api_permissions import has_school_roles
            is_student_or_guardian = has_school_roles(
                user, instance.school, {"student", "guardian"},
            )
            if is_student_or_guardian and not instance.result_published:
                for field in (
                    "auto_score", "manual_score", "final_score",
                    "teacher_feedback", "graded_by",
                ):
                    data.pop(field, None)
        return data


class ExamCommitteeSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = ExamCommittee
        fields = "__all__"


class ExamCommitteeProctorSerializer(TenantModelSerializer):
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)
    committee_name = serializers.CharField(source="committee.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = ExamCommitteeProctor
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "assigned_by", "assigned_at", "teacher_name", "committee_name",
        )


class ExamSeatingSerializer(TenantModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    committee_name = serializers.CharField(source="committee.name", read_only=True)
    secret_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(TenantModelSerializer.Meta):
        model = ExamSeating
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("student_name", "committee_name")


class SchoolBellScheduleSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = SchoolBellSchedule
        fields = "__all__"


class SchedulePeriodTemplateSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = SchedulePeriodTemplate
        fields = "__all__"


class ClassScheduleSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = ClassSchedule
        fields = "__all__"


class DailyLessonLogSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = DailyLessonLog
        fields = "__all__"


class FiscalYearSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = FiscalYear
        fields = "__all__"


class FiscalPeriodSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = FiscalPeriod
        fields = "__all__"


class AccountSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = Account
        fields = "__all__"


class CostCenterSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = CostCenter
        fields = "__all__"


class ExpenseCategorySerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = ExpenseCategory
        fields = "__all__"


class JournalEntryLineSerializer(TenantModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = JournalEntryLine
        fields = "__all__"


class JournalEntrySerializer(TenantModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)
    debit_total = serializers.SerializerMethodField()
    credit_total = serializers.SerializerMethodField()

    class Meta(TenantModelSerializer.Meta):
        model = JournalEntry
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "status", "posted_at", "posted_by", "is_reversed",
            "reversed_by_entry", "reversal_reason",
        )

    def get_debit_total(self, obj):
        return str(sum((line.debit for line in obj.lines.all()), Decimal("0.00")))

    def get_credit_total(self, obj):
        return str(sum((line.credit for line in obj.lines.all()), Decimal("0.00")))


class JournalEntryCreateSerializer(serializers.Serializer):
    fiscal_period_id = serializers.UUIDField()
    date = serializers.DateField()
    description = serializers.CharField()
    lines = serializers.ListField(child=serializers.DictField(), min_length=2)

    def validate_lines(self, lines):
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        for index, item in enumerate(lines):
            try:
                debit = Decimal(str(item.get("debit", "0")))
                credit = Decimal(str(item.get("credit", "0")))
            except Exception as exc:
                raise serializers.ValidationError(f"المبالغ في السطر {index + 1} غير صحيحة.") from exc
            if debit < 0 or credit < 0 or (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
                raise serializers.ValidationError(f"السطر {index + 1} يجب أن يحتوي مديناً أو دائناً موجباً فقط.")
            total_debit += debit
            total_credit += credit
            if not item.get("account_id"):
                raise serializers.ValidationError(f"الحساب مطلوب في السطر {index + 1}.")
        if total_debit != total_credit:
            raise serializers.ValidationError("إجمالي المدين يجب أن يساوي إجمالي الدائن.")
        return lines


class JournalEntryUpdateSerializer(serializers.Serializer):
    fiscal_period_id = serializers.UUIDField(required=False)
    date = serializers.DateField(required=False)
    description = serializers.CharField(required=False)
    lines = serializers.ListField(
        child=serializers.DictField(), min_length=2, required=False,
    )

    def validate_lines(self, lines):
        return JournalEntryCreateSerializer().validate_lines(lines)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("أرسل حقلاً واحداً على الأقل لتعديل القيد.")
        return attrs


class PaymentVoucherSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = PaymentVoucher
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("status", "journal_entry")


class ReceiptVoucherSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = ReceiptVoucher
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("status", "journal_entry")


class SupplierSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = Supplier
        fields = "__all__"


class WarehouseSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = Warehouse
        fields = "__all__"


class InventoryItemSerializer(TenantModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = InventoryItem
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "current_stock", "is_low_stock",
        )


class StockMovementSerializer(TenantModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = StockMovement
        fields = "__all__"


class PurchaseOrderItemSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = PurchaseOrderItem
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("total_price",)


class PurchaseOrderSerializer(TenantModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta(TenantModelSerializer.Meta):
        model = PurchaseOrder
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + (
            "status", "approved_by", "items", "total_amount",
        )

    def get_items(self, obj):
        return PurchaseOrderItemSerializer(obj.items.filter(is_archived=False), many=True, context=self.context).data


class VendorInvoiceSerializer(TenantModelSerializer):
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = VendorInvoice
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("paid_amount", "status", "journal_entry", "remaining_amount")


class AssetCategorySerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = AssetCategory
        fields = "__all__"


class FixedAssetSerializer(TenantModelSerializer):
    current_book_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta(TenantModelSerializer.Meta):
        model = FixedAsset
        fields = "__all__"
        read_only_fields = TenantModelSerializer.Meta.read_only_fields + ("accumulated_depreciation", "current_book_value")


class AssetDepreciationSerializer(TenantModelSerializer):
    class Meta(TenantModelSerializer.Meta):
        model = AssetDepreciationEntry
        fields = "__all__"


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["id", "school", "category", "channel", "is_enabled"]
        read_only_fields = ["id", "school"]


class PushDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = ["id", "device_id", "platform", "push_token", "app_version", "device_name", "is_active", "last_seen_at"]
        read_only_fields = ["id", "is_active", "last_seen_at"]


class ConversationParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = ["id", "user", "user_name", "phone", "role", "is_active", "is_muted", "last_read_at"]
        read_only_fields = fields


class SchoolConversationSerializer(serializers.ModelSerializer):
    participants = ConversationParticipantSerializer(many=True, read_only=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = SchoolConversation
        fields = ["id", "subject", "conversation_type", "student", "created_by", "status", "last_message_at", "participants", "unread_count", "created_at"]
        read_only_fields = fields

    def get_unread_count(self, obj):
        user = self.context["request"].user
        participant = obj.participants.filter(user=user, is_active=True).first()
        if not participant:
            return 0
        qs = obj.messages.filter(is_archived=False, is_deleted=False).exclude(sender=user)
        if participant.last_read_at:
            qs = qs.filter(created_at__gt=participant.last_read_at)
        return qs.count()


class ConversationMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    attachment_available = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    attachment_size = serializers.SerializerMethodField()

    class Meta:
        model = ConversationMessage
        fields = [
            "id", "conversation", "sender", "sender_name", "message_type",
            "body", "attachment_available", "attachment_name", "attachment_size",
            "reply_to", "created_at", "edited_at", "is_deleted",
        ]
        read_only_fields = fields

    def get_sender_name(self, obj):
        return obj.sender.get_full_name() if obj.sender_id else "النظام"

    def get_body(self, obj):
        return "" if obj.is_deleted else obj.body

    def get_attachment_available(self, obj):
        return bool(obj.attachment and not obj.is_deleted)

    def get_attachment_name(self, obj):
        if obj.is_deleted:
            return ""
        return obj.attachment_name

    def get_attachment_size(self, obj):
        return 0 if obj.is_deleted else obj.attachment_size


class ConversationCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    conversation_type = serializers.ChoiceField(choices=SchoolConversation.ConversationType.choices, default=SchoolConversation.ConversationType.GENERAL)
    student_id = serializers.UUIDField(required=False, allow_null=True)
    participant_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True, default="")
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("body") and not self.context["request"].FILES.get("attachment"):
            raise serializers.ValidationError("يجب كتابة رسالة أو إرفاق ملف.")
        return attrs

class TimetablePlanSerializer(TenantModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none(), required=False, allow_null=True)

    class Meta(TenantModelSerializer.Meta):
        model = TimetablePlan
        fields = "__all__"
        read_only_fields = tuple(field for field in TenantModelSerializer.Meta.read_only_fields if field != "branch") + (
            "version", "status", "is_current", "based_on", "submitted_by", "submitted_at",
            "approved_by", "approved_at", "published_by", "published_at",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["branch"].queryset = Branch.objects.filter(school=school, is_archived=False) if school else Branch.objects.none()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if year and school and year.school_id != school.pk:
            raise serializers.ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة النشطة."})
        if branch is None and year and year.branch_id:
            branch = year.branch
            attrs["branch"] = branch
        if branch and school and branch.school_id != school.pk:
            raise serializers.ValidationError({"branch": "الفرع لا يتبع المدرسة النشطة."})
        if year and year.branch_id and year.branch_id != getattr(branch, "pk", None):
            raise serializers.ValidationError({"branch": "الفرع لا يطابق فرع السنة الدراسية."})
        term = attrs.get("academic_term", getattr(self.instance, "academic_term", None))
        if term and year and (term.school_id != school.pk or term.academic_year_id != year.pk):
            raise serializers.ValidationError({"academic_term": "الفصل الدراسي لا يتبع السنة والمدرسة المحددتين."})
        bell = attrs.get("bell_schedule", getattr(self.instance, "bell_schedule", None))
        if bell and year and (bell.school_id != school.pk or bell.academic_year_id != year.pk):
            raise serializers.ValidationError({"bell_schedule": "قالب الجرس لا يتبع السنة والمدرسة المحددتين."})
        if bell and bell.branch_id and bell.branch_id != getattr(branch, "pk", None):
            raise serializers.ValidationError({"bell_schedule": "قالب الجرس يتبع فرعاً مختلفاً."})
        return attrs


class TimetablePlanCopyInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    effective_from = serializers.DateField(required=False)
    academic_term_id = serializers.UUIDField(required=False)
    bell_schedule_id = serializers.UUIDField(required=False)