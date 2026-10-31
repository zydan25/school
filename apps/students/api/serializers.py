from rest_framework import serializers

from apps.students.models import Guardian, Student, StudentEnrollment


class StudentEnrollmentSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = StudentEnrollment
        fields = [
            "id",
            "academic_year",
            "academic_year_name",
            "grade_level",
            "grade_level_name",
            "section",
            "section_name",
            "enrollment_date",
            "status",
            "final_result",
            "notes",
            "created_at",
        ]


class GuardianBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = Guardian
        fields = ["id", "full_name", "phone", "relationship_type", "national_id", "emergency_phone"]


class StudentListSerializer(serializers.ModelSerializer):
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "student_id_number",
            "full_name",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "grade_level",
            "grade_level_name",
            "section",
            "section_name",
            "academic_year",
            "academic_year_name",
            "status",
            "credit_balance",
            "enrollment_date",
        ]
        read_only_fields = ["credit_balance"]


class StudentDetailSerializer(StudentListSerializer):
    enrollment_history = StudentEnrollmentSerializer(many=True, read_only=True)

    class Meta(StudentListSerializer.Meta):
        fields = StudentListSerializer.Meta.fields + [
            "national_id",
            "birth_date",
            "enrollment_history",
        ]


class PromoteStudentSerializer(serializers.Serializer):
    next_academic_year_id = serializers.UUIDField(required=True)
    next_grade_level_id = serializers.UUIDField(required=True)
    next_section_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class RetainStudentSerializer(serializers.Serializer):
    next_academic_year_id = serializers.UUIDField(required=True)
    section_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class WithdrawStudentSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
