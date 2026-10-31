from rest_framework import serializers

from apps.staff.models import (
    LeaveRequest,
    LeaveType,
    StaffAttendance,
    StaffMember,
    Teacher,
)


class StaffMemberListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = StaffMember
        fields = [
            "id",
            "user",
            "full_name",
            "phone",
            "employee_number",
            "job_title",
            "role",
            "role_display",
            "assigned_floor_wing",
            "hire_date",
            "is_active",
        ]


class TeacherListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = Teacher
        fields = [
            "id",
            "user",
            "full_name",
            "phone",
            "specialization",
            "is_class_teacher",
        ]


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name", "days_allowed", "requires_attachment", "is_paid"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    applicant_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "teacher",
            "staff_member",
            "applicant_name",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "reason",
            "status",
            "status_display",
            "approved_by",
            "approved_at",
            "created_at",
        ]

    def get_applicant_name(self, obj):
        if obj.teacher:
            return obj.teacher.user.get_full_name() or obj.teacher.user.phone
        if obj.staff_member:
            return obj.staff_member.user.get_full_name() or obj.staff_member.user.phone
        return ""


class CreateLeaveRequestSerializer(serializers.Serializer):
    teacher_id = serializers.UUIDField(required=False, allow_null=True)
    staff_member_id = serializers.UUIDField(required=False, allow_null=True)
    leave_type_id = serializers.UUIDField(required=True)
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    reason = serializers.CharField(required=True, min_length=3)

    def validate(self, attrs):
        if bool(attrs.get("teacher_id")) == bool(attrs.get("staff_member_id")):
            raise serializers.ValidationError("يجب تحديد إما معلماً أو موظفاً إدارياً واحداً فقط.")
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError("تاريخ بدء الإجازة يجب أن يكون قبل أو يطابق تاريخ الانتهاء.")
        return attrs


class ApproveLeaveRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = [
            "id",
            "teacher",
            "staff_member",
            "staff_name",
            "date",
            "status",
            "status_display",
            "time_in",
            "time_out",
            "delay_minutes",
            "notes",
        ]

    def get_staff_name(self, obj):
        if obj.teacher:
            return obj.teacher.user.get_full_name() or obj.teacher.user.phone
        if obj.staff_member:
            return obj.staff_member.user.get_full_name() or obj.staff_member.user.phone
        return ""


class LogAttendanceSerializer(serializers.Serializer):
    teacher_id = serializers.UUIDField(required=False, allow_null=True)
    staff_member_id = serializers.UUIDField(required=False, allow_null=True)
    date = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=StaffAttendance.Status.choices, default=StaffAttendance.Status.PRESENT)
    time_in = serializers.TimeField(required=False, allow_null=True)
    time_out = serializers.TimeField(required=False, allow_null=True)
    delay_minutes = serializers.IntegerField(required=False, default=0, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if bool(attrs.get("teacher_id")) == bool(attrs.get("staff_member_id")):
            raise serializers.ValidationError("يجب تحديد موظف إداري أو معلم واحد فقط.")
        return attrs
