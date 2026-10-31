"""Timetable API views."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear
from apps.timetable.services.ai_generator import generate_school_timetable


class AITimetableGeneratorAPIView(APIView):
    """
    توليد جدول الحصص الأسبوعي الذكي آلياً للمدرسة.
    تدعم المعاينة (dry_run=true) أو الاعتماد والحفظ (dry_run=false).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school = getattr(request, "school", None)
        if not school:
            membership = request.user.school_memberships.filter(status="active").first()
            if membership:
                school = membership.school
        if not school and (request.user.is_superuser or request.user.is_platform_admin):
            from apps.tenants.models import School
            school_code = request.data.get("school_code") or request.query_params.get("school_code")
            if school_code:
                school = School.objects.filter(code=school_code).first()
            else:
                school = School.objects.filter(status=School.Status.ACTIVE).first()

        if not school:
            return Response({"error": "المدرسة غير محددة."}, status=status.HTTP_400_BAD_REQUEST)

        # Check permissions
        if not (request.user.is_staff or request.user.is_superuser):
            membership = request.user.school_memberships.filter(school=school, status="active").first()
            role_codes = membership.get_role_codes() if membership else set()
            if not bool(role_codes & {"school-director", "academic-coordinator", "principal", "school_admin"}):
                return Response({"error": "غير مصرح لك بتوليد الجدول المدرسي."}, status=status.HTTP_403_FORBIDDEN)

        year_id = request.data.get("academic_year_id")
        if year_id:
            academic_year = get_object_or_404(AcademicYear, id=year_id, school=school)
        else:
            academic_year = AcademicYear.objects.filter(school=school, is_active=True).first()

        if not academic_year:
            return Response({"error": "لم يتم العثور على سنة دراسية نشطة بالمدرسة."}, status=status.HTTP_400_BAD_REQUEST)

        dry_run = request.data.get("dry_run", True)
        clear_existing = request.data.get("clear_existing", False)

        result = generate_school_timetable(
            school=school,
            academic_year=academic_year,
            dry_run=dry_run,
            clear_existing=clear_existing,
        )
        return Response(result, status=status.HTTP_200_OK)
