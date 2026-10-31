"""Serializers for Attendance, Calendar, Excuses, and Scoring APIs."""
from __future__ import annotations

from rest_framework import serializers

from apps.attendance.models import (
    AttendanceExcuseRequest,
    AttendancePolicy,
    AttendanceRegister,
    AttendanceReopenRequest,
    AttendanceScoreEntry,
    AttendanceScoringPolicy,
    AttendanceStatusType,
    CalendarEvent,
    CalendarOccurrence,
    EarlyDepartureRequest,
    SchoolCalendar,
    SchoolCalendarDay,
    StudentAttendanceRecord,
)


class AttendancePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendancePolicy
        fields = [
            "id",
            "academic_year",
            "attendance_mode",
            "morning_assembly_time",
            "day_end_time",
            "grace_period_minutes",
            "late_to_absent_minutes",
            "excuse_submission_deadline_days",
            "require_excuse_attachment",
            "auto_lock_after_days",
            "allow_guardian_advance_excuse",
            "allow_guardian_post_excuse",
            "allow_guardian_early_departure",
            "is_active",
            "notes",
        ]


class AttendanceStatusTypeSerializer
    def validate(self, attrs):
        school = self.context.get("school")
        academic_year = attrs.get("academic_year") or getattr(self.instance, "academic_year", None)
        if school and academic_year and academic_year.school_id != school.pk:
            raise serializers.ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة الحالية."})
        return attrs


class AttendanceStatusTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceStatusType
        fields = [
            "id",
            "code",
            "name",
            "category",
            "color_code",
            "counts_as_present",
            "counts_as_absent",
            "is_excused",
            "is_default",
            "is_active",
            "display_order",
        ]


class StudentAttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id_number = serializers.CharField(source="student.student_id_number", read_only=True)

    def get_student_name(self, obj):
        return str(obj.student)

    class Meta:
        model = StudentAttendanceRecord
        fields = [
            "id",
            "student",
            "student_name",
            "student_id_number",
            "status_type",
            "status_category",
            "late_minutes",
            "excuse_request",
            "notes",
            "recorded_at",
        ]


class AttendanceRegisterSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.name", read_only=True)
    grade_name = serializers.CharField(source="section.grade.name", read_only=True)
    student_records = StudentAttendanceRecordSerializer(many=True, read_only=True)

    class Meta:
        model = AttendanceRegister
        fields = [
            "id",
            "academic_year",
            "academic_term",
            "section",
            "section_name",
            "grade_name",
            "date",
            "session_type",
            "schedule",
            "status",
            "submitted_at",
            "approved_at",
            "locked_at",
            "notes",
            "student_records",
        ]


class OpenRegisterInputSerializer(serializers.Serializer):
    academic_year_id = serializers.IntegerField()
    section_id = serializers.IntegerField()
    date = serializers.DateField()
    session_type = serializers.ChoiceField(
        choices=AttendanceRegister.SessionType.choices,
        default=AttendanceRegister.SessionType.DAILY_MORNING,
    )
    schedule_id = serializers.IntegerField(required=False, allow_null=True)
    bypass_calendar_check = serializers.BooleanField(default=False)


class BulkRecordItemSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    status_category = serializers.ChoiceField(choices=AttendanceStatusType.Category.choices)
    late_minutes = serializers.IntegerField(default=0, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class BulkRecordInputSerializer(serializers.Serializer):
    records = BulkRecordItemSerializer(many=True)


class AttendanceExcuseRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    guardian_name = serializers.SerializerMethodField()

    def get_student_name(self, obj):
        return str(obj.student)

    def get_guardian_name(self, obj):
        return str(obj.guardian)

    class Meta:
        model = AttendanceExcuseRequest
        fields = [
            "id",
            "student",
            "student_name",
            "guardian",
            "guardian_name",
            "request_type",
            "start_date",
            "end_date",
            "reason",
            "attachment",
            "status",
            "reviewed_at",
            "review_notes",
            "created_at",
        ]
        read_only_fields = ["status", "reviewed_at", "review_notes", "guardian"]


class ExcuseReviewInputSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField()
    review_notes = serializers.CharField(required=False, allow_blank=True, default="")


class EarlyDepartureRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    guardian_name = serializers.SerializerMethodField()

    def get_student_name(self, obj):
        return str(obj.student)

    def get_guardian_name(self, obj):
        return str(obj.guardian)

    class Meta:
        model = EarlyDepartureRequest
        fields = [
            "id",
            "student",
            "student_name",
            "guardian",
            "guardian_name",
            "date",
            "departure_time",
            "reason",
            "recipient_name",
            "recipient_phone",
            "recipient_relationship",
            "recipient_national_id",
            "status",
            "approved_at",
            "exit_confirmed_at",
            "exit_notes",
            "created_at",
        ]
        read_only_fields = ["status", "approved_at", "exit_confirmed_at", "exit_notes", "guardian"]


class GateExitInputSerializer(serializers.Serializer):
    exit_notes = serializers.CharField(required=False, allow_blank=True, default="")


class ReopenRequestInputSerializer(serializers.Serializer):
    reason = serializers.CharField()


class ReopenReviewInputSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField()
    review_notes = serializers.CharField(required=False, allow_blank=True, default="")


class SchoolCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolCalendar
        fields = [
            "id",
            "academic_year",
            "name",
            "is_central_template",
            "version",
            "is_active",
            "description",
        ]


class SchoolCalendarDaySerializer
    def validate(self, attrs):
        school = self.context.get("school")
        academic_year = attrs.get("academic_year") or getattr(self.instance, "academic_year", None)
        if school and academic_year and academic_year.school_id != school.pk:
            raise serializers.ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة الحالية."})
        return attrs


class SchoolCalendarDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolCalendarDay
        fields = [
            "id",
            "calendar",
            "date",
            "day_type",
            "title",
            "is_school_day",
            "notes",
        ]


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "academic_year",
            "title",
            "event_type",
            "recurrence_type",
            "start_date",
            "end_date",
            "day_of_week",
            "start_time",
            "end_time",
            "target_scope",
            "stage",
            "grade_level",
            "section",
            "subject",
            "teacher",
            "classroom",
            "is_active",
            "description",
        ]


class AttendanceScoringPolicySerializer
    def validate(self, attrs):
        school = self.context.get("school")
        related_fields = (
            "academic_year", "stage", "grade_level", "section",
            "subject", "teacher", "classroom",
        )
        if school:
            for field in related_fields:
                related = attrs.get(field)
                if related is None and self.instance is not None:
                    related = getattr(self.instance, field, None)
                if related is not None and related.school_id != school.pk:
                    raise serializers.ValidationError({
                        field: "السجل المرتبط لا يتبع المدرسة الحالية."
                    })

        academic_year = attrs.get("academic_year") or getattr(self.instance, "academic_year", None)
        section = attrs.get("section") or getattr(self.instance, "section", None)
        grade_level = attrs.get("grade_level") or getattr(self.instance, "grade_level", None)
        if section and academic_year and section.academic_year_id != academic_year.pk:
            raise serializers.ValidationError({"section": "الشعبة لا تنتمي إلى السنة الدراسية المحددة."})
        if section and grade_level and section.grade_id != grade_level.pk:
            raise serializers.ValidationError({"section": "الشعبة لا تتبع الصف المحدد."})
        return attrs


class AttendanceScoringPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceScoringPolicy
        fields = [
            "id",
            "academic_year",
            "subject",
            "total_attendance_score",
            "calculation_mode",
            "unexcused_absence_deduction",
            "unexcused_late_deduction",
            "excused_absence_deduction",
            "min_score",
            "is_active",
            "notes",
        ]


class AttendanceScoreEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    student_id_number = serializers.CharField(source="student.student_id_number", read_only=True)

    class Meta:
        model = AttendanceScoreEntry
        fields = [
            "id",
            "student",
            "student_name",
            "student_id_number",
            "academic_term",
            "subject",
            "raw_score",
            "unexcused_absence_count",
            "excused_absence_count",
            "late_count",
            "deduction_total",
            "final_score",
            "calculated_at",
            "is_synced_to_gradebook",
            "notes",
        ]
