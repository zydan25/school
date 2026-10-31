from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    STUDENT_AFFAIRS_ROLES,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounts.services import is_platform_operator
from apps.academics.models import AcademicYear, GradeLevel, Section
from apps.students.api.serializers import (
    PromoteStudentSerializer,
    RetainStudentSerializer,
    StudentDetailSerializer,
    StudentListSerializer,
    WithdrawStudentSerializer,
)
from apps.students.models import Student
from apps.students.services import (
    graduate_student,
    promote_student,
    retain_student,
    withdraw_student,
)


def _resolve_school(request):
    return resolve_active_school(request)


STUDENT_MANAGE_ROLES = STUDENT_AFFAIRS_ROLES | {
    "admin", "school-admin", "school_admin",
    "principal", "school-principal",
}
STUDENT_READ_ADMIN_ROLES = STUDENT_MANAGE_ROLES | {
    "registrar", "academic-coordinator", "academic_coordinator",
}


def _student_read_queryset(request, school):
    qs = Student.objects.filter(
        school=school, is_archived=False,
    ).select_related("grade_level", "section", "academic_year")
    if is_platform_operator(request.user) or has_school_roles(
        request.user, school, STUDENT_READ_ADMIN_ROLES,
    ):
        return qs

    scope = Q(pk__in=[])
    found_profile = False

    if has_school_roles(request.user, school, {"teacher"}):
        teacher = request.user.teacher_profiles.filter(
            school=school, is_archived=False,
        ).first()
        if teacher:
            found_profile = True
            section_ids = teacher.assignments.filter(
                is_archived=False,
            ).values_list("section_id", flat=True)
            scope |= Q(section_id__in=section_ids)

    if has_school_roles(request.user, school, {"guardian"}):
        guardian = request.user.guardian_profiles.filter(
            school=school, is_archived=False,
        ).first()
        if guardian:
            found_profile = True
            scope |= Q(pk__in=guardian.children.filter(
                school=school, is_archived=False,
            ).values_list("pk", flat=True))

    if has_school_roles(request.user, school, {"student"}):
        found_profile = True
        scope |= Q(user=request.user)

    if not found_profile:
        raise PermissionDenied("لا تملك دوراً أو ملفاً يسمح بعرض سجلات الطلاب.")
    return qs.filter(scope).distinct()


class StudentListAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentListSerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        return school

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StudentDetailSerializer
        return StudentListSerializer

    def get_queryset(self):
        school = self.get_school()
        qs = _student_read_queryset(self.request, school)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(middle_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(student_id_number__icontains=search)
            )
        grade_id = self.request.query_params.get("grade_level")
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        section_id = self.request.query_params.get("section")
        if section_id:
            qs = qs.filter(section_id=section_id)
        year_id = self.request.query_params.get("academic_year")
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("first_name", "last_name")

    def perform_create(self, serializer):
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, STUDENT_MANAGE_ROLES,
            "students.add_student",
        )
        data = serializer.validated_data
        if data.get("status", Student.Status.ACTIVE) != Student.Status.ACTIVE:
            raise ValidationError(
                "ينشأ الطالب بحالة نشطة؛ استخدم إجراءات القيد المخصصة لتغيير الحالة."
            )

        year = get_object_or_404(
            AcademicYear, pk=data["academic_year"].pk, school=school,
            is_archived=False,
        )
        grade = get_object_or_404(
            GradeLevel, pk=data["grade_level"].pk, school=school,
            is_archived=False, is_active=True,
        )
        if year.status not in {
            AcademicYear.Status.PLANNING, AcademicYear.Status.ACTIVE,
        }:
            raise PermissionDenied(
                "لا يمكن تسجيل طالب في سنة دراسية مغلقة أو مؤرشفة."
            )

        with transaction.atomic():
            # Serialize capacity checks for concurrent registrations in this section.
            section = get_object_or_404(
                Section.objects.select_for_update(),
                pk=data["section"].pk, school=school,
                is_archived=False, is_active=True,
            )
            if section.grade_id != grade.pk or section.academic_year_id != year.pk:
                raise PermissionDenied(
                    "يجب أن تتبع الشعبة الصف والسنة الدراسية المحددين."
                )
            if section.is_full:
                raise ValidationError(
                    "الشعبة ممتلئة؛ افتح شعبة جديدة أو زِد سعتها قبل تسجيل الطالب."
                )

            student = Student(
                school=school,
                academic_year=year,
                grade_level=grade,
                section=section,
                student_id_number=data["student_id_number"].strip(),
                first_name=data["first_name"].strip(),
                middle_name=data.get("middle_name", "").strip(),
                last_name=data["last_name"].strip(),
                gender=data.get("gender", Student.Gender.MALE),
                national_id=data.get("national_id", ""),
                birth_date=data.get("birth_date"),
                enrollment_date=data.get("enrollment_date") or timezone.localdate(),
                status=Student.Status.ACTIVE,
            )
            student.full_clean()
            student.save()
            serializer.instance = student



class StudentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentDetailSerializer
    lookup_url_kwarg = "pk"

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def get_queryset(self):
        return _student_read_queryset(self.request, self.get_school()).prefetch_related(
            "enrollment_history__academic_year",
            "enrollment_history__grade_level",
            "enrollment_history__section",
        )

    def perform_update(self, serializer):
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, STUDENT_MANAGE_ROLES,
            "students.change_student",
        )
        lifecycle_fields = {
            "academic_year", "grade_level", "section", "status",
            "enrollment_date",
        }
        changed_lifecycle_fields = []
        for field in lifecycle_fields:
            if field not in serializer.validated_data:
                continue
            new_value = serializer.validated_data[field]
            current_value = getattr(serializer.instance, field)
            old_value = getattr(current_value, "pk", current_value)
            new_value = getattr(new_value, "pk", new_value)
            if old_value != new_value:
                changed_lifecycle_fields.append(field)
        if changed_lifecycle_fields:
            raise ValidationError({
                "detail": (
                    "لا تغيّر الصف أو الشعبة أو السنة أو حالة القيد من تعديل الملف؛ "
                    "استخدم إجراءات الترفيع أو إعادة القيد أو التخرج أو الانسحاب."
                ),
                "fields": sorted(changed_lifecycle_fields),
            })
        serializer.save()

    def perform_destroy(self, instance):
        require_school_role_or_permission(
            self.request, self.get_school(), STUDENT_MANAGE_ROLES,
            "students.delete_student",
        )
        instance.archive(actor=self.request.user, reason="أرشفة الطالب عبر API")


class StudentPromoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        serializer = PromoteStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        next_year = get_object_or_404(AcademicYear, pk=data["next_academic_year_id"], school=school)
        next_grade = get_object_or_404(GradeLevel, pk=data["next_grade_level_id"], school=school)
        next_section = None
        if data.get("next_section_id"):
            next_section = get_object_or_404(Section, pk=data["next_section_id"], school=school)

        student, enrollment = promote_student(
            student=student,
            next_academic_year=next_year,
            next_grade_level=next_grade,
            next_section=next_section,
            user=request.user,
            notes=data.get("notes", ""),
        )
        return Response({
            "message": f"تم ترفيع الطالب {student} إلى {next_grade.name} بنجاح.",
            "student_id": str(student.pk),
            "academic_year": next_year.name,
            "grade_level": next_grade.name,
        }, status=status.HTTP_200_OK)


class StudentRetainAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        serializer = RetainStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        next_year = get_object_or_404(AcademicYear, pk=data["next_academic_year_id"], school=school)
        section = None
        if data.get("section_id"):
            section = get_object_or_404(Section, pk=data["section_id"], school=school)

        student, enrollment = retain_student(
            student=student,
            next_academic_year=next_year,
            section=section,
            user=request.user,
            notes=data.get("notes", ""),
        )
        return Response({
            "message": f"تم إعادة قيد الطالب {student} للعام {next_year.name} بنجاح.",
            "student_id": str(student.pk),
            "academic_year": next_year.name,
        }, status=status.HTTP_200_OK)


class StudentGraduateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        notes = request.data.get("notes", "")
        student = graduate_student(student=student, user=request.user, notes=notes)
        return Response({
            "message": f"تم تخريج الطالب {student} بنجاح.",
            "student_id": str(student.pk),
            "status": student.status,
        }, status=status.HTTP_200_OK)


class StudentWithdrawAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        serializer = WithdrawStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        student = withdraw_student(student=student, reason=reason, user=request.user)
        return Response({
            "message": f"تم توثيق انسحاب الطالب {student} بنجاح.",
            "student_id": str(student.pk),
            "status": student.status,
        }, status=status.HTTP_200_OK)
