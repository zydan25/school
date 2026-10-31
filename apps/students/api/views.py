from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    if getattr(request, "school", None):
        return request.school
    from apps.accounts.services import is_platform_operator
    from apps.tenants.models import School
    school_id = request.headers.get("X-School-ID") or request.query_params.get("school_id")
    school_code = request.headers.get("X-School-Code") or request.query_params.get("school_code")
    if is_platform_operator(request.user):
        if school_id:
            return School.objects.filter(pk=school_id, status=School.Status.ACTIVE).first()
        if school_code:
            return School.objects.filter(code=school_code.upper(), status=School.Status.ACTIVE).first()
        return School.objects.filter(status=School.Status.ACTIVE).first()
    memberships = request.user.school_memberships.filter(status="active", school__status=School.Status.ACTIVE)
    if school_id:
        m = memberships.filter(school_id=school_id).first()
        return m.school if m else None
    if school_code:
        m = memberships.filter(school__code=school_code.upper()).first()
        return m.school if m else None
    first_m = memberships.first()
    return first_m.school if first_m else None


class StudentListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentListSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        qs = Student.objects.filter(school=school, is_archived=False).select_related(
            "grade_level", "section", "academic_year"
        )
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                first_name__icontains=search
            ) | qs.filter(last_name__icontains=search) | qs.filter(student_id_number__icontains=search)
        grade_id = self.request.query_params.get("grade_level")
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        section_id = self.request.query_params.get("section")
        if section_id:
            qs = qs.filter(section_id=section_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("first_name", "last_name")


class StudentDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentDetailSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        return Student.objects.filter(school=school, is_archived=False).select_related(
            "grade_level", "section", "academic_year"
        ).prefetch_related("enrollment_history__academic_year", "enrollment_history__grade_level", "enrollment_history__section")


class StudentPromoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
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
