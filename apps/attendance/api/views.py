"""REST API Views and ViewSets for Attendance Domain."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicTerm, AcademicYear, Section, Subject
from apps.attendance.api.serializers import (
    AttendanceExcuseRequestSerializer,
    AttendancePolicySerializer,
    AttendanceRegisterSerializer,
    AttendanceScoreEntrySerializer,
    AttendanceScoringPolicySerializer,
    AttendanceStatusTypeSerializer,
    BulkRecordInputSerializer,
    CalendarEventSerializer,
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
    EarlyDepartureRequest,
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


class BaseAttendanceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        return school


class AttendancePolicyViewSet(BaseAttendanceViewSet):
    serializer_class = AttendancePolicySerializer

    def get_queryset(self):
        return AttendancePolicy.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AttendanceStatusTypeViewSet(BaseAttendanceViewSet):
    serializer_class = AttendanceStatusTypeSerializer

    def get_queryset(self):
        return AttendanceStatusType.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("display_order")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AttendanceRegisterViewSet(BaseAttendanceViewSet):
    serializer_class = AttendanceRegisterSerializer

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

        return qs.order_by("-date", "-created_at")

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

    def get_queryset(self):
        qs = AttendanceExcuseRequest.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).select_related("student", "guardian")

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        guardian = Guardian.objects.filter(school=school, user=self.request.user).first()
        if not guardian and not self.request.user.is_staff:
            raise ValidationError("المستخدم الحالي ليس لديه ملف ولي أمر مرتبط.")

        data = serializer.validated_data
        guardian_obj = data.get("guardian") or guardian
        try:
            create_excuse_request(
                school=school,
                student=data["student"],
                guardian=guardian_obj,
                request_type=data["request_type"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                reason=data["reason"],
                attachment=self.request.FILES.get("attachment"),
            )
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

    def get_queryset(self):
        qs = EarlyDepartureRequest.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).select_related("student", "guardian")

        date_param = self.request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)

        return qs.order_by("-date", "-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        guardian = Guardian.objects.filter(school=school, user=self.request.user).first()
        if not guardian and not self.request.user.is_staff:
            raise ValidationError("المستخدم الحالي ليس لديه ملف ولي أمر مرتبط.")

        data = serializer.validated_data
        guardian_obj = data.get("guardian") or guardian
        try:
            create_early_departure_request(
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


class CalendarEventViewSet(BaseAttendanceViewSet):
    serializer_class = CalendarEventSerializer

    def get_queryset(self):
        return CalendarEvent.objects.filter(
            school=self.get_school(),
            is_archived=False,
        ).order_by("-start_date")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AttendanceScoringViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate_score(self, request):
        school = self.get_school()
        student_id = request.data.get("student_id")
        term_id = request.data.get("academic_term_id")
        subject_id = request.data.get("subject_id")

        if not student_id or not term_id:
            raise ValidationError("student_id و academic_term_id مطلوبان.")

        student = get_object_or_404(Student, pk=student_id, school=school)
        term = get_object_or_404(AcademicTerm, pk=term_id, school=school)
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

        entries = recalculate_term_scores(school, term, section, subject)
        return Response({"message": f"تم احتساب درجات المواظبة لـ {len(entries)} طالب بنجاح."})

    @action(detail=True, methods=["post"], url_path="sync-gradebook")
    def sync_to_gradebook_action(self, request, pk=None):
        school = self.get_school()
        entry = get_object_or_404(AttendanceScoreEntry, pk=pk, school=school)
        gradebook = sync_score_to_gradebook(entry)
        if not gradebook:
            raise ValidationError("تعذر مزامنة الدرجة، تأكد من توفر مادة دراسية صالحة.")
        return Response({"message": "تم ترحيل درجة المواظبة بنجاح إلى سجل الدرجات العام.", "score": entry.final_score})


class AttendanceReportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def get(self, request, report_type):
        school = self.get_school()
        export_format = request.query_params.get("export")

        if report_type == "daily-summary":
            date_str = request.query_params.get("date", str(datetime.date.today()))
            section_id = request.query_params.get("section_id")
            try:
                date = datetime.date.fromisoformat(date_str)
            except ValueError:
                date = datetime.date.today()

            summaries = get_daily_section_summary(school, date, section_id=section_id)
            if export_format == "csv":
                csv_data = export_daily_summary_to_csv(summaries)
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="attendance_daily_{date}.csv"'
                return response
            return Response({"date": str(date), "summaries": summaries})

        elif report_type == "monthly-matrix":
            section_id = request.query_params.get("section_id")
            year = int(request.query_params.get("year", datetime.date.today().year))
            month = int(request.query_params.get("month", datetime.date.today().month))
            if not section_id:
                raise ValidationError("section_id مطلوب لكشف الحضور الشهري.")

            matrix = get_monthly_attendance_matrix(school, int(section_id), year, month)
            return Response(matrix)

        elif report_type == "term-summary":
            term_id = request.query_params.get("academic_term_id")
            section_id = request.query_params.get("section_id")
            if not term_id:
                raise ValidationError("academic_term_id مطلوب.")

            res = get_term_attendance_summary(school, int(term_id), section_id=int(section_id) if section_id else None)
            return Response({"results": res})

        elif report_type == "chronic-absenteeism":
            year_id = request.query_params.get("academic_year_id")
            threshold = float(request.query_params.get("threshold", 10.0))
            if not year_id:
                raise ValidationError("academic_year_id مطلوب لكشف الإنذار المبكر.")

            cases = get_chronic_absenteeism_report(school, int(year_id), threshold_percentage=threshold)
            if export_format == "csv":
                csv_data = export_chronic_absenteeism_to_csv(cases)
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = 'attachment; filename="chronic_absenteeism.csv"'
                return response
            return Response({"cases": cases, "count": len(cases)})

        else:
            raise ValidationError("نوع التقرير غير مدعوم.")
