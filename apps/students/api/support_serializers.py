"""Serializers for student incident, summon and complaint APIs."""
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import SchoolMembership, User
from apps.staff.models import Teacher
from apps.students.models import (
    AdministrativeSummon,
    Guardian,
    SchoolComplaint,
    Student,
    StudentGuardianRelation,
    StudentIncidentReport,
)


def active_school_user_queryset(school):
    now = timezone.now()
    return User.objects.filter(
        school_memberships__school=school,
        school_memberships__status=SchoolMembership.Status.ACTIVE,
    ).filter(
        Q(school_memberships__expires_at__isnull=True)
        | Q(school_memberships__expires_at__gt=now)
    ).distinct()


class StudentSupportTenantSerializer(serializers.ModelSerializer):
    """Shared tenant and related-object validation for student support records."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        if not school:
            return attrs

        model = self.Meta.model
        for model_field in model._meta.fields:
            if not model_field.is_relation or not (
                model_field.many_to_one or model_field.one_to_one
            ):
                continue
            related = attrs.get(model_field.name)
            if related is None and self.instance is not None:
                related = getattr(self.instance, model_field.name, None)
            related_school_id = getattr(related, "school_id", None) if related else None
            if related_school_id is not None and str(related_school_id) != str(school.pk):
                raise serializers.ValidationError({
                    model_field.name: "العنصر المرتبط لا يتبع المدرسة النشطة."
                })
        return attrs


class StudentIncidentReportSerializer(StudentSupportTenantSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    reporter_name = serializers.CharField(source="reporter.get_full_name", read_only=True)

    class Meta:
        model = StudentIncidentReport
        fields = "__all__"
        read_only_fields = (
            "id", "school", "branch", "reporter", "parent_notified",
            "parent_seen_at", "is_resolved", "created_at", "updated_at",
            "is_archived", "archived_at", "archived_by",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        if school:
            self.fields["student"].queryset = Student.objects.filter(
                school=school, is_archived=False
            )


class IncidentResolutionSerializer(serializers.Serializer):
    action_taken = serializers.CharField(required=True, allow_blank=False, max_length=10000)


class AdministrativeSummonSerializer(StudentSupportTenantSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True, allow_null=True)
    target_name = serializers.CharField(source="target_user.get_full_name", read_only=True)
    issued_by_name = serializers.CharField(source="issued_by.get_full_name", read_only=True)

    class Meta:
        model = AdministrativeSummon
        fields = "__all__"
        read_only_fields = (
            "id", "school", "branch", "issued_by", "is_attended",
            "attended_at", "session_minutes", "created_at", "updated_at",
            "is_archived", "archived_at", "archived_by",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        if school:
            self.fields["target_user"].queryset = active_school_user_queryset(school)
            self.fields["student"].queryset = Student.objects.filter(
                school=school, is_archived=False
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        target = attrs.get("target_user", getattr(self.instance, "target_user", None))
        student = attrs.get("student", getattr(self.instance, "student", None))
        summon_type = attrs.get(
            "summon_type", getattr(self.instance, "summon_type", None)
        )
        if not school or not target:
            return attrs

        if not active_school_user_queryset(school).filter(pk=target.pk).exists():
            raise serializers.ValidationError({
                "target_user": "المستدعى لا يملك عضوية نشطة وسارية في المدرسة."
            })

        if summon_type in {
            AdministrativeSummon.TargetType.GUARDIAN,
            AdministrativeSummon.TargetType.STUDENT,
        } and student is None:
            raise serializers.ValidationError({
                "student": "يجب تحديد الطالب المرتبط بهذا الاستدعاء."
            })

        if summon_type == AdministrativeSummon.TargetType.GUARDIAN:
            linked = StudentGuardianRelation.objects.filter(
                school=school,
                student=student,
                guardian__user=target,
                guardian__is_archived=False,
                is_archived=False,
            ).exists()
            if not linked:
                raise serializers.ValidationError({
                    "target_user": "المستخدم المحدد ليس ولي أمر مرتبطاً بالطالب."
                })
        elif summon_type == AdministrativeSummon.TargetType.STUDENT:
            if student.user_id != target.pk:
                raise serializers.ValidationError({
                    "target_user": "حساب المستدعى لا يطابق حساب الطالب المحدد."
                })
        elif summon_type == AdministrativeSummon.TargetType.TEACHER:
            if not Teacher.objects.filter(
                school=school, user=target, is_archived=False
            ).exists():
                raise serializers.ValidationError({
                    "target_user": "المستخدم المحدد لا يملك ملف معلم في المدرسة."
                })
            if student is not None:
                raise serializers.ValidationError({
                    "student": "لا يربط استدعاء المعلم بطالب."
                })
        return attrs


class AdministrativeSummonTargetSerializer(serializers.ModelSerializer):
    """Limited view for the summoned person; internal minutes are not disclosed."""

    student_name = serializers.CharField(source="student.get_full_name", read_only=True, allow_null=True)
    class Meta:
        model = AdministrativeSummon
        fields = (
            "id", "summon_type", "student", "student_name", "reason",
            "appointment_date", "location", "is_attended", "attended_at",
            "created_at",
        )
        read_only_fields = fields


class SummonAttendanceSerializer(serializers.Serializer):
    session_minutes = serializers.CharField(required=False, allow_blank=True, max_length=10000)


class SchoolComplaintSerializer(StudentSupportTenantSerializer):
    submitter_name = serializers.CharField(
        source="submitter.get_full_name", read_only=True, allow_null=True
    )
    resolved_by_name = serializers.CharField(
        source="resolved_by.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = SchoolComplaint
        fields = "__all__"
        read_only_fields = (
            "id", "school", "branch", "submitter", "status",
            "resolution_notes", "resolved_by", "resolved_at",
            "created_at", "updated_at", "is_archived", "archived_at",
            "archived_by",
        )


class ComplaintReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(
        SchoolComplaint.Status.IN_REVIEW,
        SchoolComplaint.Status.RESOLVED,
        SchoolComplaint.Status.CLOSED,
    ))
    resolution_notes = serializers.CharField(required=False, allow_blank=True, max_length=10000)
