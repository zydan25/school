from rest_framework import serializers

from apps.students.models import Guardian, Student, StudentEnrollment, StudentMovement


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


class StudentSafeListSerializer(serializers.ModelSerializer):
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Student
        fields = [
            "id", "student_id_number", "full_name", "first_name",
            "middle_name", "last_name", "gender", "grade_level",
            "grade_level_name", "section", "section_name", "academic_year",
            "academic_year_name", "status", "enrollment_date",
        ]
        read_only_fields = fields


class StudentSafeDetailSerializer(StudentSafeListSerializer):
    enrollment_history = StudentEnrollmentSerializer(many=True, read_only=True)

    class Meta(StudentSafeListSerializer.Meta):
        fields = StudentSafeListSerializer.Meta.fields + ["enrollment_history"]
        read_only_fields = fields


class StudentAdminSafeDetailSerializer(serializers.ModelSerializer):
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    enrollment_history = StudentEnrollmentSerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            "id", "student_id_number", "full_name", "first_name",
            "middle_name", "last_name", "gender", "national_id",
            "birth_date", "grade_level", "grade_level_name", "section",
            "section_name", "academic_year", "academic_year_name",
            "status", "enrollment_date", "enrollment_history",
        ]
        read_only_fields = [
            "id", "full_name", "grade_level_name", "section_name",
            "academic_year_name", "status", "enrollment_history",
        ]


class StudentDetailSerializer(StudentListSerializer):
    enrollment_history = StudentEnrollmentSerializer(many=True, read_only=True)

    class Meta(StudentListSerializer.Meta):
        fields = StudentListSerializer.Meta.fields + [
            "national_id",
            "birth_date",
            "enrollment_history",
        ]


class StudentMovementSerializer(serializers.ModelSerializer):
    movement_type_display = serializers.CharField(
        source="get_movement_type_display", read_only=True,
    )
    previous_year_name = serializers.CharField(
        source="previous_academic_year.name", read_only=True, allow_null=True,
    )
    previous_grade_name = serializers.CharField(
        source="previous_grade_level.name", read_only=True, allow_null=True,
    )
    previous_section_name = serializers.CharField(
        source="previous_section.name", read_only=True, allow_null=True,
    )
    next_year_name = serializers.CharField(
        source="next_academic_year.name", read_only=True, allow_null=True,
    )
    next_grade_name = serializers.CharField(
        source="next_grade_level.name", read_only=True, allow_null=True,
    )
    next_section_name = serializers.CharField(
        source="next_section.name", read_only=True, allow_null=True,
    )
    recorded_by_name = serializers.CharField(
        source="recorded_by.get_full_name", read_only=True, allow_null=True,
    )

    class Meta:
        model = StudentMovement
        fields = [
            "id", "movement_type", "movement_type_display", "effective_date",
            "previous_year_name", "previous_grade_name", "previous_section_name",
            "next_year_name", "next_grade_name", "next_section_name",
            "reason", "recorded_by_name", "created_at",
        ]
        read_only_fields = fields


class StudentTransferSerializer(serializers.Serializer):
    target_section_id = serializers.UUIDField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=5000, default="")


class StudentImportRowSerializer(serializers.Serializer):
    student_id_number = serializers.CharField(max_length=50, trim_whitespace=True)
    first_name = serializers.CharField(max_length=100, trim_whitespace=True)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=100, trim_whitespace=True)
    gender = serializers.ChoiceField(choices=Student.Gender.choices, default=Student.Gender.MALE)
    academic_year_id = serializers.UUIDField()
    grade_level_id = serializers.UUIDField()
    section_id = serializers.UUIDField()
    enrollment_date = serializers.DateField(required=False, allow_null=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    national_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        school = self.context["school"]
        from apps.academics.models import AcademicYear, GradeLevel, Section

        year = AcademicYear.objects.filter(
            pk=attrs["academic_year_id"], school=school, is_archived=False,
            status__in=[AcademicYear.Status.PLANNING, AcademicYear.Status.ACTIVE],
        ).first()
        grade = GradeLevel.objects.filter(
            pk=attrs["grade_level_id"], school=school, is_archived=False,
            is_active=True,
        ).first()
        section = Section.objects.filter(
            pk=attrs["section_id"], school=school, is_archived=False,
            is_active=True,
        ).first()
        if year is None:
            raise serializers.ValidationError({"academic_year_id": "السنة الدراسية غير متاحة في المدرسة."})
        if grade is None:
            raise serializers.ValidationError({"grade_level_id": "الصف الدراسي غير متاح في المدرسة."})
        if section is None:
            raise serializers.ValidationError({"section_id": "الشعبة غير متاحة في المدرسة."})
        if section.academic_year_id != year.pk or section.grade_id != grade.pk:
            raise serializers.ValidationError({"section_id": "الشعبة لا تتبع الصف والسنة المحددين."})
        attrs["academic_year"] = year
        attrs["grade_level"] = grade
        attrs["section"] = section
        return attrs


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
