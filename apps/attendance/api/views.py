"""REST API Views and ViewSets for Attendance Domain."""
from __future__ import annotations

import datetime
from uuid import UUID

from django.db.models import Q
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
from apps.tenants.models import Branch
from apps.accounts.api_permissions import has_school_roles, require_school_role_or_permission
from apps.attendance.api.serializers import (
    AttendanceAuditLogSerializer,
    AttendanceExcuseRequestSerializer,
    AttendancePolicySerializer,
    AttendanceReopenRequestSerializer,
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
    AttendanceAuditLog,
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
from apps.staff.models import TeacherAssignment
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
        qs = AttendancePolicy.objects.filter(
            school=self.get_school(), is_archived=False,
        )
        branch_id = self.request.query_params.get("branch_id")
        if branch_id:
            try:
                branch_uuid = UUID(str(branch_id))
            except (TypeError, ValueError, AttributeError):
                raise ValidationError({"branch_id": "أرسل معرف فرع صحيحاً بصيغة UUID."})
            branch = Branch.objects.filter(pk=branch_uuid, school=self.get_school(), is_archived=False).first()
            if branch is None:
                raise ValidationError({"branch_id": "الفرع غير موجود أو لا يتبع المدرسة النشطة."})
            qs = qs.filter(Q(branch=branch) | Q(branch__isnull=True))
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        academic_year = serializer.validated_data["academic_year"]
        branch = serializer.validated_data.get("branch")
        if branch is None and academic_year.branch_id:
            branch = academic_year.branch
        serializer.save(school=self.get_school(), branch=branch)


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
        ).select_related("section", "section__grade", "academic_year", "academic_term", "branch", "schedule")

        date_param = self.request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)

        section_param = self.request.query_params.get("section_id")
        if section_param:
            qs = qs.filter(section_id=section_param)

        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not has_school_roles(
            self.request.user, self.get_school(), ATTENDANCE_ADMIN_ROLES
        ):
            teacher = self.request.user.teacher_profiles.filter(school=self.get_school(), is_active_teaching=True).first()
            assigned_sections = TeacherAssignment.objects.filter(
                school=self.get_school(), teacher=teacher, is_archived=False,
            ).values_list("section_id", flat=True) if teacher else []
            qs = qs.filter(section_id__in=assigned_sections) if teacher else qs.none()
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
        year = get_object_or_404(AcademicYear, pk=data["academic_year_id"], school=school, is_archived=False)
        section = get_object_or_404(Section, pk=data["section_id"], school=school, academic_year=year, is_archived=False)

        schedule = None
        if data.get("schedule_id"):
            schedule = get_object_or_404(ClassSchedule, pk=data["schedule_id"], school=school, section=section, academic_year=year, is_archived=False)

        if has_school_roles(request.user, school, {"teacher"}) and not has_school_roles(
            request.user, school, ATTENDANCE_ADMIN_ROLES
        ):
            teacher = request.user.teacher_profiles.filter(school=school, is_active_teaching=True).first()
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك في المدرسة المحددة.")
            if schedule and schedule.teacher_id != teacher.pk:
                raise PermissionDenied("لا يمكنك فتح سجل حضور لحصة مسندة إلى معلم آخر.")
            assignments = TeacherAssignment.objects.filter(
                school=school, academic_year=year, section=section, teacher=teacher, is_archived=False,
            )
            if schedule:
                assignments = assignments.filter(subject=schedule.subject)
            if section.branch_id:
                assignments = assignments.filter(Q(branch=section.branch) | Q(branch__isnull=True))
            else:
                assignments = assignments.filter(branch__isnull=True)
            if not assignments.exists():
                raise PermissionDenied("لا يمكنك فتح سجل حضور دون إسناد نشط لهذه الشعبة والسنة.")

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
        queryset = SchoolCalendar.objects.filter(
            school=self.get_school(),
            is_archived=False,
        )
        branch_id = self.request.query_params.get("branch_id")
        if branch_id:
            try:
                branch_uuid = UUID(str(branch_id))
            except (TypeError, ValueError, AttributeError):
                raise ValidationError({"branch_id": "أرسل معرف فرع صحيحاً بصيغة UUID."})
            branch = Branch.objects.filter(
                pk=branch_uuid, school=self.get_school(), is_archived=False,
            ).first()
            if branch is None:
                raise ValidationError({"branch_id": "الفرع غير موجود أو لا يتبع المدرسة النشطة."})
            queryset = queryset.filter(Q(branch_id=branch.pk) | Q(branch__isnull=True))
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())

    @action(detail=True, methods=["post"], url_path="seed-days")
    def seed_days(self, request, pk=None):
        cal = self.get_object()
        seed_default_calendar(
            school=cal.school, academic_year=cal.academic_year,
            name=cal.name, branch=cal.branch,
        )
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
        branch_id = self.request.query_params.get("branch_id")
        if branch_id:
            try:
                branch_uuid = UUID(str(branch_id))
            except (TypeError, ValueError, AttributeError):
                raise ValidationError({"branch_id": "أرسل معرف فرع صحيحاً بصيغة UUID."})
            branch = Branch.objects.filter(
                pk=branch_uuid, school=self.get_school(), is_archived=False,
            ).first()
            if branch is None:
                raise ValidationError({"branch_id": "الفرع غير موجود أو لا يتبع المدرسة النشطة."})
            qs = qs.filter(Q(calendar__branch_id=branch.pk) | Q(calendar__branch__isnull=True))
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
        calendar = serializer.validated_data["calendar"]
        serializer.save(school=self.get_school(), branch=calendar.branch)

    def perform_update(self, serializer):
        calendar = serializer.validated_data.get("calendar", serializer.instance.calendar)
        serializer.save(school=self.get_school(), branch=calendar.branch)


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

class AttendanceReopenRequestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AttendanceReopenRequestSerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("حدد مدرسة نشطة تملك عضوية سارية فيها.")
        return school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_school_role_or_permission(request, self.get_school(), ATTENDANCE_READ_ROLES)

    def get_queryset(self):
        qs = AttendanceReopenRequest.objects.filter(
            school=self.get_school(), is_archived=False
        ).select_related("register", "register__section", "requested_by", "reviewed_by").order_by("-created_at")
        if not has_school_roles(self.request.user, self.get_school(), ATTENDANCE_ADMIN_ROLES):
            qs = qs.filter(requested_by=self.request.user)
        status_filter = self.request.query_params.get("status")
        register_id = self.request.query_params.get("register_id")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if register_id:
            qs = qs.filter(register_id=register_id)
        return qs


class AttendanceAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AttendanceAuditLogSerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("حدد مدرسة نشطة تملك عضوية سارية فيها.")
        return school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_school_role_or_permission(request, self.get_school(), ATTENDANCE_ADMIN_ROLES)

    def get_queryset(self):
        qs = AttendanceAuditLog.objects.filter(
            school=self.get_school()
        ).select_related(
            "register", "register__section", "student_record", "student_record__student", "performed_by"
        ).order_by("-timestamp")
        register_id = self.request.query_params.get("register_id")
        student_id = self.request.query_params.get("student_id")
        action_code = self.request.query_params.get("action")
        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if register_id:
            qs = qs.filter(register_id=register_id)
        if student_id:
            qs = qs.filter(student_record__student_id=student_id)
        if action_code:
            qs = qs.filter(action=action_code)
        try:
            start_value = datetime.date.fromisoformat(date_from) if date_from else None
            end_value = datetime.date.fromisoformat(date_to) if date_to else None
        except (TypeError, ValueError):
            raise ValidationError("صيغة فترة سجل التدقيق غير صحيحة؛ استخدم YYYY-MM-DD.")
        if start_value and end_value and end_value < start_value:
            raise ValidationError("تاريخ نهاية فترة التدقيق يسبق بدايتها.")
        if start_value:
            qs = qs.filter(register__date__gte=start_value)
        if end_value:
            qs = qs.filter(register__date__lte=end_value)
        return qs


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
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("حدد مدرسة نشطة تملك عضوية سارية فيها.")
        return school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_school_role_or_permission(request, self.get_school(), ATTENDANCE_ADMIN_ROLES)

    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate_score(self, request):
        school = self.get_school()
        student_id = request.data.get("student_id")
        term_id = request.data.get("academic_term_id")
        subject_id = request.data.get("subject_id")
        if not student_id or not term_id:
            raise ValidationError("student_id و academic_term_id مطلوبان.")

        student = get_object_or_404(Student, pk=student_id, school=school, is_archived=False)
        term = get_object_or_404(AcademicTerm, pk=term_id, school=school)
        if student.academic_year_id != term.academic_year_id:
            raise ValidationError("الفصل الدراسي لا يتبع العام الحالي للطالب.")
        subject = get_object_or_404(Subject, pk=subject_id, school=school) if subject_id else None
        entry = calculate_student_attendance_score(school, student, term, subject)
        return Response(AttendanceScoreEntrySerializer(entry).data)

    @action(detail=False, methods=["post"], url_path="recalculate-term")
    def recalculate_term(self, request):
        school = self.get_school()
        term_id = request.data.get("academic_term_id")
        section_id = request.data.get("section_id")
        subject_id = request.data.get("subject_id")
        if not term_id:
            raise ValidationError("academic_term_id مطلوب.")

        term = get_object_or_404(AcademicTerm, pk=term_id, school=school)
        section = get_object_or_404(Section, pk=section_id, school=school) if section_id else None
        subject = get_object_or_404(Subject, pk=subject_id, school=school) if subject_id else None
        if section and section.academic_year_id != term.academic_year_id:
            raise ValidationError("الشعبة لا تنتمي إلى العام الدراسي لهذا الفصل.")
        entries = recalculate_term_scores(school, term, section, subject)
        return Response({"message": f"تم احتساب درجات المواظبة لـ {len(entries)} طالب بنجاح.", "count": len(entries)})

    @action(detail=True, methods=["post"], url_path="sync-gradebook")
    def sync_to_gradebook_action(self, request, pk=None):
        school = self.get_school()
        entry = get_object_or_404(AttendanceScoreEntry, pk=pk, school=school, is_archived=False)
        gradebook = sync_score_to_gradebook(entry)
        if not gradebook:
            raise ValidationError("تعذر مزامنة الدرجة؛ تحقق من توفر مادة دراسية نشطة.")
        return Response({
            "message": "تم ترحيل درجة المواظبة بنجاح إلى سجل الدرجات العام.",
            "score": str(entry.final_score),
            "gradebook_id": str(gradebook.pk),
        })


class MyChildrenAttendanceAPIView(APIView):
    """سجل حضور الأبناء المرتبطين حصراً بولي الأمر المصادق عليه."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("حدد المدرسة النشطة أولاً.")
        guardian = Guardian.objects.filter(school=school, user=request.user).first()
        if not guardian:
            raise PermissionDenied("هذه الخدمة متاحة لحساب ولي الأمر فقط.")

        children = guardian.children.filter(
            school=school, is_archived=False
        ).select_related("section", "grade_level").order_by("first_name", "last_name")
        student_id = request.query_params.get("student_id")
        if student_id:
            children = children.filter(pk=student_id)
            if not children.exists():
                raise PermissionDenied("الطالب المحدد ليس من الأبناء المرتبطين بحسابك.")

        records = StudentAttendanceRecord.objects.filter(
            school=school, student__in=children, is_archived=False
        ).select_related("student", "register", "register__section").order_by(
            "-register__date", "-recorded_at"
        )
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        try:
            start_value = datetime.date.fromisoformat(date_from) if date_from else None
            end_value = datetime.date.fromisoformat(date_to) if date_to else None
        except (TypeError, ValueError):
            raise ValidationError("صيغة التاريخ غير صحيحة؛ استخدم YYYY-MM-DD.")
        if start_value and end_value and end_value < start_value:
            raise ValidationError("تاريخ نهاية الفترة يسبق تاريخ بدايتها.")
        if start_value:
            records = records.filter(register__date__gte=start_value)
        if end_value:
            records = records.filter(register__date__lte=end_value)

        rows = [{
            "id": str(record.pk),
            "student_id": str(record.student_id),
            "student_name": str(record.student),
            "section": record.register.section.name,
            "date": record.register.date.isoformat(),
            "session_type": record.register.session_type,
            "status": record.status_category,
            "late_minutes": record.late_minutes,
            "notes": record.notes,
            "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
        } for record in records[:250]]
        return Response({
            "children": [{
                "id": str(child.pk),
                "student_number": child.student_id_number,
                "name": str(child),
                "section": child.section.name if child.section_id else None,
            } for child in children],
            "results": rows,
            "count": len(rows),
        })


class MyChildrenAttendanceScoresAPIView(APIView):
    """درجات المواظبة الفصلية للأبناء المرتبطين بولي الأمر الحالي فقط."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("حدد المدرسة النشطة أولاً.")
        guardian = Guardian.objects.filter(school=school, user=request.user).first()
        if not guardian:
            raise PermissionDenied("هذه الخدمة متاحة لحساب ولي الأمر فقط.")

        children = guardian.children.filter(school=school, is_archived=False)
        student_id = request.query_params.get("student_id")
        if student_id:
            children = children.filter(pk=student_id)
            if not children.exists():
                raise PermissionDenied("الطالب المحدد ليس من الأبناء المرتبطين بحسابك.")

        entries = AttendanceScoreEntry.objects.filter(
            school=school, student__in=children, is_archived=False
        ).select_related("student", "academic_term", "subject").order_by(
            "-academic_term__starts_on", "student__first_name"
        )
        term_id = request.query_params.get("academic_term_id")
        if term_id:
            entries = entries.filter(academic_term_id=term_id)

        rows = [{
            "id": str(entry.pk),
            "student_id": str(entry.student_id),
            "student_name": str(entry.student),
            "academic_term_id": str(entry.academic_term_id),
            "academic_term": entry.academic_term.name,
            "subject_id": str(entry.subject_id) if entry.subject_id else None,
            "subject": entry.subject.name if entry.subject_id else None,
            "raw_score": str(entry.raw_score),
            "unexcused_absence_count": entry.unexcused_absence_count,
            "excused_absence_count": entry.excused_absence_count,
            "late_count": entry.late_count,
            "deduction_total": str(entry.deduction_total),
            "final_score": str(entry.final_score),
            "calculated_at": entry.calculated_at.isoformat() if entry.calculated_at else None,
        } for entry in entries[:250]]
        return Response({"results": rows, "count": len(rows)})


class AttendanceReportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def _uuid_param(self, value, field_name):
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError({field_name: "أرسل معرفاً صحيحاً بصيغة UUID."})

    def get(self, request, report_type):
        school = self.get_school()
        require_school_role_or_permission(request, school, ATTENDANCE_ADMIN_ROLES)
        export_format = request.query_params.get("export")

        if report_type == "daily-summary":
            date_str = request.query_params.get("date", timezone.localdate().isoformat())
            try:
                report_date = datetime.date.fromisoformat(date_str)
            except (TypeError, ValueError):
                raise ValidationError({"date": "صيغة التاريخ غير صحيحة؛ استخدم YYYY-MM-DD."})
            section_id = request.query_params.get("section_id")
            if section_id:
                section_uuid = self._uuid_param(section_id, "section_id")
                get_object_or_404(Section, pk=section_uuid, school=school, is_archived=False)
            summaries = get_daily_section_summary(school, report_date, section_id=section_id)
            if export_format == "csv":
                csv_data = export_daily_summary_to_csv(summaries)
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="attendance_daily_{report_date}.csv"'
                return response
            return Response({"date": report_date.isoformat(), "summaries": summaries})

        if report_type == "monthly-matrix":
            section_id = request.query_params.get("section_id")
            if not section_id:
                raise ValidationError({"section_id": "section_id مطلوب لكشف الحضور الشهري."})
            section_uuid = self._uuid_param(section_id, "section_id")
            section = get_object_or_404(Section, pk=section_uuid, school=school, is_archived=False)
            try:
                year = int(request.query_params.get("year", timezone.localdate().year))
                month = int(request.query_params.get("month", timezone.localdate().month))
            except (TypeError, ValueError):
                raise ValidationError("السنة والشهر يجب أن يكونا أرقاماً صحيحة.")
            if year < 1 or year > 9999:
                raise ValidationError({"year": "السنة خارج النطاق الصحيح."})
            if month < 1 or month > 12:
                raise ValidationError({"month": "الشهر يجب أن يكون بين 1 و12."})
            matrix = get_monthly_attendance_matrix(school, section.pk, year, month)
            return Response(matrix)

        if report_type == "term-summary":
            term_id = request.query_params.get("academic_term_id")
            if not term_id:
                raise ValidationError({"academic_term_id": "academic_term_id مطلوب."})
            term_uuid = self._uuid_param(term_id, "academic_term_id")
            term = get_object_or_404(AcademicTerm, pk=term_uuid, school=school, is_archived=False)
            section_id = request.query_params.get("section_id")
            section_uuid = None
            if section_id:
                section_uuid = self._uuid_param(section_id, "section_id")
                section = get_object_or_404(Section, pk=section_uuid, school=school, is_archived=False)
                if section.academic_year_id != term.academic_year_id:
                    raise ValidationError({"section_id": "الشعبة لا تتبع السنة الدراسية للفصل المحدد."})
            try:
                results = get_term_attendance_summary(school, term.pk, section_id=section_uuid)
            except ValueError as exc:
                raise ValidationError(detail=str(exc))
            return Response({"results": results})

        if report_type == "chronic-absenteeism":
            year_id = request.query_params.get("academic_year_id")
            if not year_id:
                raise ValidationError({"academic_year_id": "academic_year_id مطلوب لكشف الإنذار المبكر."})
            year_uuid = self._uuid_param(year_id, "academic_year_id")
            academic_year = get_object_or_404(AcademicYear, pk=year_uuid, school=school, is_archived=False)
            try:
                threshold = float(request.query_params.get("threshold", 10.0))
            except (TypeError, ValueError):
                raise ValidationError({"threshold": "حد الغياب المزمن يجب أن يكون رقماً."})
            if not 0 <= threshold <= 100:
                raise ValidationError({"threshold": "حد الغياب المزمن يجب أن يكون بين 0 و100 بالمائة."})
            try:
                cases = get_chronic_absenteeism_report(school, academic_year.pk, threshold_percentage=threshold)
            except ValueError as exc:
                raise ValidationError(detail=str(exc))
            if export_format == "csv":
                csv_data = export_chronic_absenteeism_to_csv(cases)
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = 'attachment; filename="chronic_absenteeism.csv"'
                return response
            return Response({"cases": cases, "count": len(cases)})

        raise ValidationError({"report_type": "نوع التقرير غير مدعوم."})
