"""REST API Views and ViewSets for Attendance Domain."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicTerm, AcademicYear, Section, Subject
from apps.accounts.api_permissions import has_school_roles, require_school_role_or_permission
from apps.attendance.api.serializers import (
    AttendanceExcuseRequestSerializer,
    AttendancePolicySerializer,
    AttendanceRegisterSerializer,
    AttendanceScoreEntrySerializer,
    AttendanceScoringPolicySerializer,
    AttendanceStatusTypeSerializer,
    BulkRecordInputSerializer,
    CalendarEventSerializer,
    CalendarOccurrenceSerializer,
    EarlyDepartureRequestSerializer,
    ExcuseReviewInputSerializer,
    GateExitInputSerializer,
    OpenRegisterInputSerializer,
    ReopenRequestInputSerializer,
    ReopenReviewInputSerializer,
    SchoolCalendarDaySerializer,
    SchoolCalendarSerializer,
)
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
    StudentAttendanceRecord,
    SchoolCalendar,
    SchoolCalendarDay,
)
from apps.attendance.reports.exports import (
    export_chronic_absenteeism_to_csv,
    export_daily_summary_to_csv,
)
from apps.attendance.reports.selectors import (
    get_chronic_absenteeism_report,
    get_daily_section_summary,
    get_monthly_attendance_matrix,
    get_term_attendance_summary,
)
from apps.attendance.services import (
    approve_early_departure,
    approve_register,
    bulk_record_attendance,
    calculate_student_attendance_score,
    confirm_gate_exit,
    create_early_departure_request,
    create_excuse_request,
    get_or_create_register,
    generate_event_occurrences,
    lock_register,
    recalculate_term_scores,
    request_reopen_register,
    review_excuse_request,
    review_reopen_request,
    seed_default_calendar,
    submit_register,
    sync_score_to_gradebook,
)
from apps.students.api.views import _resolve_school
from apps.students.models import Guardian, Student
from apps.timetable.models import ClassSchedule


ATTENDANCE_ADMIN_ROLES = {
    "school-director", "school_director",
    "academic-coordinator", "academic_coordinator",
    "student-affairs", "student_affairs",
}
ATTENDANCE_READ_ROLES = ATTENDANCE_ADMIN_ROLES | {"teacher"}
ATTENDANCE_TEACHER_ROLES = ATTENDANCE_ADMIN_ROLES | {"teacher"}
ATTENDANCE_GATE_ROLES = ATTENDANCE_ADMIN_ROLES | {"gate-security", "gate_security", "school-gate-guard"}


class BaseAttendanceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    action_role_map: dict[str, set[str]] = {}
    special_access_actions: set[str] = set()

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("حدد مدرسة نشطة تملك عضوية سارية فيها.")
        return school

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def perform_destroy(self, instance):
        # Treat API DELETE as archive, preserving records referenced by history.
        instance.is_archived = True
        fields = ["is_archived"]
        if hasattr(instance, "is_active"):
            instance.is_active = False
            fields.append("is_active")
        if hasattr(instance, "updated_at"):
            fields.append("updated_at")
        instance.save(update_fields=fields)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = self.get_school()
        if self.action in self.special_access_actions:
            return
        allowed_roles = self.action_role_map.get(
            self.action,
            ATTENDANCE_READ_ROLES if self.action == "metadata" else ATTENDANCE_ADMIN_ROLES,
        )
        require_school_role_or_permission(request, school, allowed_roles)

class AttendancePolicyViewSet(BaseAttendanceViewSet):
    serializer_class = AttendancePolicySerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "create": ATTENDANCE_ADMIN_ROLES, "update": ATTENDANCE_ADMIN_ROLES,
        "partial_update": ATTENDANCE_ADMIN_ROLES, "destroy": ATTENDANCE_ADMIN_ROLES,
    }

    def get_queryset(self):
        return AttendancePolicy.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AttendanceStatusTypeViewSet(BaseAttendanceViewSet):
    serializer_class = AttendanceStatusTypeSerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "create": ATTENDANCE_ADMIN_ROLES, "update": ATTENDANCE_ADMIN_ROLES,
        "partial_update": ATTENDANCE_ADMIN_ROLES, "destroy": ATTENDANCE_ADMIN_ROLES,
    }

    def get_queryset(self):
        return AttendanceStatusType.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("display_order")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AttendanceRegisterViewSet(BaseAttendanceViewSet):
    serializer_class = AttendanceRegisterSerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "open_register": ATTENDANCE_TEACHER_ROLES,
        "bulk_record": ATTENDANCE_TEACHER_ROLES,
        "submit_action": ATTENDANCE_TEACHER_ROLES,
        "reopen_request": ATTENDANCE_TEACHER_ROLES,
        "approve_action": ATTENDANCE_ADMIN_ROLES,
        "lock_action": ATTENDANCE_ADMIN_ROLES,
        "review_reopen": ATTENDANCE_ADMIN_ROLES,
    }

    def get_queryset(self):
        qs = AttendanceRegister.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).select_related("section", "section__grade", "academic_year", "academic_term")

        date_param = self.request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)

        section_param = self.request.query_params.get("section_id")
        if section_param:
            qs = qs.filter(section_id=section_param)

        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not has_school_roles(
            self.request.user, self.get_school(), ATTENDANCE_ADMIN_ROLES
        ):
            teacher = self.request.user.teacher_profiles.filter(school=self.get_school()).first()
            assigned_sections = teacher.assignments.filter(is_archived=False).values_list("section_id", flat=True) if teacher else []
            qs = qs.filter(section_id__in=assigned_sections)
        return qs.order_by("-date", "-created_at")

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="استخدم POST /registers/open/ لتهيئة سجل الحضور.")

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT", detail="استخدم bulk-record ودورة الاعتماد لتعديل الرصد.")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH", detail="استخدم bulk-record ودورة الاعتماد لتعديل الرصد.")

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="لا يجوز حذف سجل حضور؛ استخدم طلب إعادة الفتح.")

    @action(detail=False, methods=["post"], url_path="open")
    def open_register(self, request):
        serializer = OpenRegisterInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = self.get_school()
        year = get_object_or_404(AcademicYear, pk=data["academic_year_id"], school=school)
        section = get_object_or_404(Section, pk=data["section_id"], school=school)

        schedule = None
        if data.get("schedule_id"):
            schedule = get_object_or_404(ClassSchedule, pk=data["schedule_id"], school=school)

        if has_school_roles(request.user, school, {"teacher"}) and not has_school_roles(
            request.user, school, ATTENDANCE_ADMIN_ROLES
        ):
            teacher = request.user.teacher_profiles.filter(school=school).first()
            assigned = teacher.assignments.filter(
                section_id=section.pk, is_archived=False
            ).exists() if teacher else False
            if not assigned:
                raise PermissionDenied("لا يمكنك فتح سجل حضور لشعبة غير مسندة إليك.")

        if data.get("bypass_calendar_check"):
            require_school_role_or_permission(request, school, ATTENDANCE_ADMIN_ROLES)
        try:
            register, created = get_or_create_register(
                school=school,
                academic_year=year,
                section=section,
                date=data["date"],
                session_type=data["session_type"],
                schedule=schedule,
                user=request.user,
                bypass_calendar_check=data.get("bypass_calendar_check", False),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        output = AttendanceRegisterSerializer(register)
        return Response(output.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="bulk-record")
    def bulk_record(self, request, pk=None):
        register = self.get_object()
        serializer = BulkRecordInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        records_data = serializer.validated_data["records"]

        try:
            count = bulk_record_attendance(
                register=register,
                records_data=records_data,
                recorded_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response({"message": "تم رصد وتحديث الحضور بنجاح.", "updated_records": count})

    @action(detail=True, methods=["post"], url_path="submit")
    def submit_action(self, request, pk=None):
        register = self.get_object()
        try:
            reg = submit_register(
                register=register,
                submitted_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response(AttendanceRegisterSerializer(reg).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve_action(self, request, pk=None):
        register = self.get_object()
        try:
            reg = approve_register(
                register=register,
                approved_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response(AttendanceRegisterSerializer(reg).data)

    @action(detail=True, methods=["post"], url_path="lock")
    def lock_action(self, request, pk=None):
        register = self.get_object()
        try:
            reg = lock_register(
                register=register,
                locked_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response(AttendanceRegisterSerializer(reg).data)

    @action(detail=True, methods=["post"], url_path="reopen-request")
    def reopen_request(self, request, pk=None):
        register = self.get_object()
        serializer = ReopenRequestInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            req = request_reopen_register(
                register=register,
                requested_by=request.user,
                reason=serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response({"message": "تم إرسال طلب إعادة الفتح للمراجعة.", "request_id": req.id})

    @action(detail=True, methods=["post"], url_path="review-reopen")
    def review_reopen(self, request, pk=None):
        register = self.get_object()
        reopen_req = register.reopen_requests.filter(status=AttendanceReopenRequest.Status.PENDING).first()
        if not reopen_req:
            raise ValidationError("لا يوجد طلب إعادة فتح معلق لهذا السجل.")

        serializer = ReopenReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review_reopen_request(
            reopen_request=reopen_req,
            reviewed_by=request.user,
            is_approved=serializer.validated_data["is_approved"],
            review_notes=serializer.validated_data.get("review_notes", ""),
        )
        return Response({"message": "تمت معالجة طلب إعادة الفتح بنجاح."})


class AttendanceExcuseRequestViewSet(BaseAttendanceViewSet):
    serializer_class = AttendanceExcuseRequestSerializer
    special_access_actions = {"list", "retrieve", "create"}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = self.get_school()
        guardian = Guardian.objects.filter(school=school, user=request.user).first()
        if self.action == "create":
            if guardian is None:
                raise PermissionDenied("تقديم العذر متاح لولي الأمر المرتبط بالطالب فقط.")
        elif self.action in {"list", "retrieve"}:
            if guardian is None and not has_school_roles(request.user, school, ATTENDANCE_ADMIN_ROLES):
                raise PermissionDenied("لا تملك صلاحية عرض طلبات الأعذار.")
        elif self.action == "review_action":
            require_school_role_or_permission(request, school, ATTENDANCE_ADMIN_ROLES)
        else:
            raise MethodNotAllowed(request.method)

    def get_queryset(self):
        qs = AttendanceExcuseRequest.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).select_related("student", "guardian")

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        if not has_school_roles(self.request.user, self.get_school(), ATTENDANCE_ADMIN_ROLES):
            guardian = Guardian.objects.filter(school=self.get_school(), user=self.request.user).first()
            qs = qs.filter(guardian=guardian) if guardian else qs.none()
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        guardian = Guardian.objects.filter(school=school, user=self.request.user).first()
        if not guardian:
            raise PermissionDenied("لا يوجد ملف ولي أمر مرتبط بحسابك في هذه المدرسة.")
        data = serializer.validated_data
        guardian_obj = guardian
        try:
            created_request = create_excuse_request(
                school=school,
                student=data["student"],
                guardian=guardian_obj,
                request_type=data["request_type"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                reason=data["reason"],
                attachment=self.request.FILES.get("attachment"),
            )
            serializer.instance = created_request
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

    @action(detail=True, methods=["post"], url_path="review")
    def review_action(self, request, pk=None):
        excuse_req = self.get_object()
        serializer = ExcuseReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            review_excuse_request(
                excuse_request=excuse_req,
                reviewed_by=request.user,
                is_approved=serializer.validated_data["is_approved"],
                review_notes=serializer.validated_data.get("review_notes", ""),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response(AttendanceExcuseRequestSerializer(excuse_req).data)


class EarlyDepartureRequestViewSet(BaseAttendanceViewSet):
    serializer_class = EarlyDepartureRequestSerializer
    special_access_actions = {"list", "retrieve", "create"}
    action_role_map = {
        "approve_action": ATTENDANCE_ADMIN_ROLES,
        "confirm_gate_exit_action": ATTENDANCE_GATE_ROLES,
    }

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = self.get_school()
        guardian = Guardian.objects.filter(school=school, user=request.user).first()
        if self.action == "create":
            if guardian is None:
                raise PermissionDenied("طلب الانصراف متاح لولي الأمر المرتبط بالطالب فقط.")
        elif self.action in {"list", "retrieve"}:
            if guardian is None and not has_school_roles(request.user, school, ATTENDANCE_GATE_ROLES):
                raise PermissionDenied("لا تملك صلاحية عرض طلبات الانصراف.")
        elif self.action == "approve_action":
            require_school_role_or_permission(request, school, ATTENDANCE_ADMIN_ROLES)
        elif self.action == "confirm_gate_exit_action":
            require_school_role_or_permission(request, school, ATTENDANCE_GATE_ROLES)
        else:
            raise MethodNotAllowed(request.method)

    def get_queryset(self):
        qs = EarlyDepartureRequest.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).select_related("student", "guardian")

        date_param = self.request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)

        if not has_school_roles(self.request.user, self.get_school(), ATTENDANCE_ADMIN_ROLES):
            if has_school_roles(self.request.user, self.get_school(), ATTENDANCE_GATE_ROLES):
                return qs.order_by("-date", "-created_at")
            guardian = Guardian.objects.filter(school=self.get_school(), user=self.request.user).first()
            qs = qs.filter(guardian=guardian) if guardian else qs.none()
        return qs.order_by("-date", "-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        guardian = Guardian.objects.filter(school=school, user=self.request.user).first()
        if not guardian:
            raise PermissionDenied("لا يوجد ملف ولي أمر مرتبط بحسابك في هذه المدرسة.")
        data = serializer.validated_data
        guardian_obj = guardian
        try:
            created_request = create_early_departure_request(
                school=school,
                student=data["student"],
                guardian=guardian_obj,
                date=data["date"],
                departure_time=data["departure_time"],
                reason=data["reason"],
                recipient_name=data["recipient_name"],
                recipient_phone=data["recipient_phone"],
                recipient_relationship=data["recipient_relationship"],
                recipient_national_id=data.get("recipient_national_id", ""),
            )
            serializer.instance = created_request
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

    @action(detail=True, methods=["post"], url_path="approve")
    def approve_action(self, request, pk=None):
        req_obj = self.get_object()
        approve_early_departure(req_obj, approved_by=request.user)
        return Response(EarlyDepartureRequestSerializer(req_obj).data)

    @action(detail=True, methods=["post"], url_path="confirm-gate-exit")
    def confirm_gate_exit_action(self, request, pk=None):
        req_obj = self.get_object()
        serializer = GateExitInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            confirm_gate_exit(
                departure_request=req_obj,
                confirmed_by=request.user,
                exit_notes=serializer.validated_data.get("exit_notes", ""),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

        return Response(EarlyDepartureRequestSerializer(req_obj).data)


class SchoolCalendarViewSet(BaseAttendanceViewSet):
    serializer_class = SchoolCalendarSerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "create": ATTENDANCE_ADMIN_ROLES, "update": ATTENDANCE_ADMIN_ROLES,
        "partial_update": ATTENDANCE_ADMIN_ROLES, "destroy": ATTENDANCE_ADMIN_ROLES,
        "seed_days": ATTENDANCE_ADMIN_ROLES,
    }

    def get_queryset(self):
        return SchoolCalendar.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="seed-days")
    def seed_days(self, request, pk=None):
        cal = self.get_object()
        seed_default_calendar(school=cal.school, academic_year=cal.academic_year, name=cal.name)
        return Response({"message": "تم إنشاء وتصنيف أيام التقويم الدراسي بنجاح."})


class SchoolCalendarDayViewSet(BaseAttendanceViewSet):
    serializer_class = SchoolCalendarDaySerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "create": ATTENDANCE_ADMIN_ROLES, "update": ATTENDANCE_ADMIN_ROLES,
        "partial_update": ATTENDANCE_ADMIN_ROLES, "destroy": ATTENDANCE_ADMIN_ROLES,
    }

    def get_queryset(self):
        qs = SchoolCalendarDay.objects.filter(
            school=self.get_school(),
            calendar__school=self.get_school(),
            is_archived=False,
        ).select_related("calendar").order_by("date")
        calendar_id = self.request.query_params.get("calendar_id")
        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if calendar_id:
            qs = qs.filter(calendar_id=calendar_id)
        try:
            start_value = datetime.date.fromisoformat(date_from) if date_from else None
            end_value = datetime.date.fromisoformat(date_to) if date_to else None
        except (TypeError, ValueError):
            raise ValidationError("صيغة فترة التقويم غير صحيحة؛ استخدم YYYY-MM-DD.")
        if start_value and end_value and end_value < start_value:
            raise ValidationError("تاريخ نهاية الفترة يسبق تاريخ بدايتها.")
        if start_value:
            qs = qs.filter(date__gte=start_value)
        if end_value:
            qs = qs.filter(date__lte=end_value)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class CalendarEventViewSet(BaseAttendanceViewSet):
    serializer_class = CalendarEventSerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "create": ATTENDANCE_ADMIN_ROLES, "update": ATTENDANCE_ADMIN_ROLES,
        "partial_update": ATTENDANCE_ADMIN_ROLES, "destroy": ATTENDANCE_ADMIN_ROLES,
        "generate_occurrences": ATTENDANCE_ADMIN_ROLES,
        "occurrences": ATTENDANCE_READ_ROLES,
    }

    def get_queryset(self):
        return CalendarEvent.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("-start_date")

    def perform_create(self, serializer):
        with transaction.atomic():
            event = serializer.save(school=self.get_school())
            generate_event_occurrences(event)

    @action(detail=True, methods=["get"], url_path="occurrences")
    def occurrences(self, request, pk=None):
        event = self.get_object()
        occurrences = CalendarOccurrence.objects.filter(
            school=self.get_school(), event=event, is_archived=False
        ).order_by("date", "start_time")
        return Response(CalendarOccurrenceSerializer(occurrences, many=True).data)

    @action(detail=True, methods=["post"], url_path="generate-occurrences")
    def generate_occurrences(self, request, pk=None):
        event = self.get_object()
        created = generate_event_occurrences(event)
        return Response({
            "event_id": str(event.pk),
            "created_count": len(created),
            "occurrences": CalendarOccurrenceSerializer(created, many=True).data,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class AttendanceScoringPolicyViewSet(BaseAttendanceViewSet):
    serializer_class = AttendanceScoringPolicySerializer
    action_role_map = {
        "list": ATTENDANCE_READ_ROLES, "retrieve": ATTENDANCE_READ_ROLES,
        "create": ATTENDANCE_ADMIN_ROLES, "update": ATTENDANCE_ADMIN_ROLES,
        "partial_update": ATTENDANCE_ADMIN_ROLES, "destroy": ATTENDANCE_ADMIN_ROLES,
    }

    def get_queryset(self):
        qs = AttendanceScoringPolicy.objects.filter(
            school=self.get_school(), is_archived=False
        ).select_related("academic_year", "subject").order_by("academic_year__starts_on", "subject__name")
        year_id = self.request.query_params.get("academic_year_id")
        subject_id = self.request.query_params.get("subject_id")
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AttendanceScoreEntryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AttendanceScoreEntrySerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("حدد مدرسة نشطة تملك عضوية سارية فيها.")
        return school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_school_role_or_permission(request, self.get_school(), ATTENDANCE_READ_ROLES)

    def get_queryset(self):
        qs = AttendanceScoreEntry.objects.filter(
            school=self.get_school(), is_archived=False
        ).select_related("student", "academic_term", "subject").order_by(
            "-calculated_at", "student__first_name"
        )
        student_id = self.request.query_params.get("student_id")
        term_id = self.request.query_params.get("academic_term_id")
        section_id = self.request.query_params.get("section_id")
        if student_id:
            qs = qs.filter(student_id=student_id)
        if term_id:
            qs = qs.filter(academic_term_id=term_id)
        if section_id:
            qs = qs.filter(student__section_id=section_id)
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not has_school_roles(
            self.request.user, self.get_school(), ATTENDANCE_ADMIN_ROLES
        ):
            teacher = self.request.user.teacher_profiles.filter(school=self.get_school()).first()
            section_ids = teacher.assignments.filter(is_archived=False).values_list("section_id", flat=True) if teacher else []
            qs = qs.filter(student__section_id__in=section_ids)
        return qs


class AttendanceScoringViewSet(viewsets.ViewSet):

class AttendanceReportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def get(self, request, report_type):
        school = self.get_school()
        require_school_role_or_permission(request, school, ATTENDANCE_ADMIN_ROLES)
        export_format = request.query_params.get("export")

        if report_type == "daily-summary":
            date_str = request.query_params.get("date", timezone.localdate().isoformat())
            section_id = request.query_params.get("section_id")
            try:
                date = datetime.date.fromisoformat(date_str)
            except (TypeError, ValueError):
                raise ValidationError("صيغة التاريخ غير صحيحة؛ استخدم YYYY-MM-DD.")

            summaries = get_daily_section_summary(school, date, section_id=section_id)
            if export_format == "csv":
                csv_data = export_daily_summary_to_csv(summaries)
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="attendance_daily_{date}.csv"'
                return response
            return Response({"date": str(date), "summaries": summaries})

        elif report_type == "monthly-matrix":
            section_id = request.query_params.get("section_id")
            try:
                year = int(request.query_params.get("year", timezone.localdate().year))
                month = int(request.query_params.get("month", timezone.localdate().month))
            except (TypeError, ValueError):
                raise ValidationError("السنة والشهر يجب أن يكونا أرقاماً صحيحة.")
            if not section_id:
                raise ValidationError("section_id مطلوب لكشف الحضور الشهري.")
            if month < 1 or month > 12:
                raise ValidationError("الشهر يجب أن يكون بين 1 و12.")

            matrix = get_monthly_attendance_matrix(school, int(section_id), year, month)
            return Response(matrix)

        elif report_type == "term-summary":
            term_id = request.query_params.get("academic_term_id")
            section_id = request.query_params.get("section_id")
            if not term_id:
                raise ValidationError("academic_term_id مطلوب.")
            try:
                term_id_value = int(term_id)
                section_id_value = int(section_id) if section_id else None
            except (TypeError, ValueError):
                raise ValidationError("معرف الفصل أو الشعبة غير صحيح.")

            res = get_term_attendance_summary(school, term_id_value, section_id=section_id_value)
            return Response({"results": res})

        elif report_type == "chronic-absenteeism":
            year_id = request.query_params.get("academic_year_id")
            try:
                year_id_value = int(year_id) if year_id else None
                threshold = float(request.query_params.get("threshold", 10.0))
            except (TypeError, ValueError):
                raise ValidationError("السنة والحد النسبي يجب أن يكونا رقماً صحيحاً.")
            if not year_id_value:
                raise ValidationError("academic_year_id مطلوب لكشف الإنذار المبكر.")
            if threshold < 0 or threshold > 100:
                raise ValidationError("حد الغياب المزمن يجب أن يكون بين 0 و100 بالمائة.")

            cases = get_chronic_absenteeism_report(school, year_id_value, threshold_percentage=threshold)
            if export_format == "csv":
                csv_data = export_chronic_absenteeism_to_csv(cases)
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = 'attachment; filename="chronic_absenteeism.csv"'
                return response
            return Response({"cases": cases, "count": len(cases)})

        else:
            raise ValidationError("نوع التقرير غير مدعوم.")
