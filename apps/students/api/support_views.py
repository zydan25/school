"""Additional endpoints for support records owned by apps.students.

Existing student CRUD and lifecycle endpoints remain in views.py unchanged.
"""
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
    resolve_active_school,
)
from apps.accounts.services import is_platform_operator
from apps.notifications.services import create_in_app_notification
from apps.staff.models import Teacher
from apps.students.api.support_serializers import (
    AdministrativeSummonSerializer,
    AdministrativeSummonTargetSerializer,
    ComplaintReviewSerializer,
    IncidentResolutionSerializer,
    SchoolComplaintSerializer,
    StudentIncidentReportSerializer,
    SummonAttendanceSerializer,
)
from apps.students.models import (
    AdministrativeSummon,
    Guardian,
    SchoolComplaint,
    Student,
    StudentGuardianRelation,
    StudentIncidentReport,
)


MANAGE_ROLES = STUDENT_AFFAIRS_ROLES | {
    "admin", "school-admin", "school_admin",
    "principal", "school-principal", "registrar",
}
TEACHER_ROLES = {"teacher"}
FAMILY_ROLES = {"guardian", "student"}


def get_school(request):
    school = resolve_active_school(request)
    if not school:
        raise PermissionDenied("حدد المدرسة النشطة وتأكد من أن عضويتك سارية.")
    return school


def is_manager(user, school):
    return is_platform_operator(user) or has_school_roles(user, school, MANAGE_ROLES)


def linked_student_ids(user, school):
    student_ids = set(
        Student.objects.filter(
            school=school, user=user, is_archived=False
        ).values_list("pk", flat=True)
    )
    guardian_ids = Guardian.objects.filter(
        school=school, user=user, is_archived=False
    ).values_list("pk", flat=True)
    student_ids.update(
        StudentGuardianRelation.objects.filter(
            school=school,
            guardian_id__in=guardian_ids,
            is_archived=False,
            student__is_archived=False,
        ).values_list("student_id", flat=True)
    )
    return student_ids


def require_teacher_assigned_to_student(user, school, student):
    teacher = Teacher.objects.filter(
        school=school, user=user, is_archived=False
    ).first()
    if not teacher or not teacher.assignments.filter(
        school=school, section=student.section, is_archived=False
    ).exists():
        raise PermissionDenied("لا يمكنك تسجيل بلاغ إلا لطالب في شعبة مسندة إليك.")


class StudentIncidentListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentIncidentReportSerializer

    def get_school(self):
        return get_school(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def get_queryset(self):
        school = self.get_school()
        qs = StudentIncidentReport.objects.filter(
            school=school, is_archived=False
        ).select_related("student", "reporter")
        if is_manager(self.request.user, school):
            return qs.order_by("-date", "-created_at")

        visible = Q(pk__in=[])
        role_found = False
        if has_school_roles(self.request.user, school, TEACHER_ROLES):
            role_found = True
            visible |= Q(reporter=self.request.user)
        if has_school_roles(self.request.user, school, {"guardian"}):
            role_found = True
            visible |= Q(
                student_id__in=linked_student_ids(self.request.user, school),
                parent_notified=True,
            )
        if has_school_roles(self.request.user, school, {"student"}):
            role_found = True
            visible |= Q(
                student__user=self.request.user,
                parent_notified=True,
            )
        if not role_found:
            raise PermissionDenied("لا تملك صلاحية عرض بلاغات الطلاب.")
        return qs.filter(visible).distinct().order_by("-date", "-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        if not (
            is_manager(self.request.user, school)
            or has_school_roles(self.request.user, school, TEACHER_ROLES)
        ):
            raise PermissionDenied("إنشاء البلاغات متاح للمعلم والإدارة المخولة فقط.")
        student = serializer.validated_data["student"]
        if not is_manager(self.request.user, school):
            require_teacher_assigned_to_student(
                self.request.user, school, student
            )
        serializer.save(school=school, reporter=self.request.user)


class StudentIncidentDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentIncidentReportSerializer
    lookup_url_kwarg = "pk"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = get_school(self.request)
        return context

    def get_queryset(self):
        return StudentIncidentListCreateAPIView(
            request=self.request
        ).get_queryset()


class StudentIncidentNotifyParentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        school = get_school(request)
        incident = get_object_or_404(
            StudentIncidentReport.objects.select_for_update(),
            pk=pk, school=school, is_archived=False,
        )
        allowed = is_manager(request.user, school) or (
            incident.reporter_id == request.user.id
            and has_school_roles(request.user, school, TEACHER_ROLES)
        )
        if not allowed:
            raise PermissionDenied("لا تملك صلاحية نشر هذا البلاغ لأولياء الأمور.")

        with transaction.atomic():
            incident = get_object_or_404(
                StudentIncidentReport.objects.select_for_update(),
                pk=pk, school=school, is_archived=False,
            )
            relations = StudentGuardianRelation.objects.filter(
                school=school,
                student=incident.student,
                is_archived=False,
                receives_notifications=True,
                guardian__is_archived=False,
            ).select_related("guardian__user")
            sent_count = 0
            for relation in relations:
                recipient = relation.guardian.user
                notification, created = create_in_app_notification(
                    recipient=recipient,
                    school=school,
                    category="student_incident",
                    title="إشعار بخصوص الطالب",
                    body=f"يوجد بلاغ جديد بخصوص الطالب {incident.student.get_full_name()}: {incident.title}",
                    action_url=f"/students/incidents/{incident.pk}/",
                    payload={"incident_id": str(incident.pk), "student_id": str(incident.student_id)},
                    idempotency_key=f"student-incident:{incident.pk}:guardian:{recipient.pk}",
                )
                if created:
                    sent_count += 1
            if not incident.parent_notified:
                incident.parent_notified = True
                incident.save(update_fields=["parent_notified", "updated_at"])
        return Response({
            "incident_id": str(incident.pk),
            "parent_portal_notifications_created": sent_count,
            "published": incident.parent_notified,
        }, status=status.HTTP_200_OK)


class StudentIncidentSeenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        school = get_school(request)
        incident = get_object_or_404(
            StudentIncidentReport.objects.select_related("student"),
            pk=pk, school=school, is_archived=False,
            parent_notified=True,
        )
        if not (
            is_manager(request.user, school)
            or incident.student_id in linked_student_ids(request.user, school)
        ):
            raise PermissionDenied("لا يمكنك تأكيد الاطلاع على بلاغ لا يخص أبناءك.")
        if incident.parent_seen_at is None:
            incident.parent_seen_at = timezone.now()
            incident.save(update_fields=["parent_seen_at", "updated_at"])
        return Response({
            "incident_id": str(incident.pk),
            "parent_seen_at": incident.parent_seen_at,
        })


class StudentIncidentResolveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        school = get_school(request)
        if not is_manager(request.user, school):
            raise PermissionDenied("معالجة البلاغات متاحة لإدارة شؤون الطلاب فقط.")
        serializer = IncidentResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = get_object_or_404(
            StudentIncidentReport.objects.select_for_update(),
            pk=pk, school=school, is_archived=False,
        )
        incident.action_taken = serializer.validated_data["action_taken"]
        incident.is_resolved = True
        incident.save(update_fields=["action_taken", "is_resolved", "updated_at"])
        return Response(StudentIncidentReportSerializer(
            incident, context={"school": school}
        ).data)


class AdministrativeSummonListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdministrativeSummonSerializer

    def get_school(self):
        return get_school(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def get_queryset(self):
        school = self.get_school()
        qs = AdministrativeSummon.objects.filter(
            school=school, is_archived=False
        ).select_related("student", "target_user", "issued_by")
        if is_manager(self.request.user, school):
            return qs.order_by("-appointment_date")
        return qs.filter(target_user=self.request.user).order_by("-appointment_date")

    def get_serializer_class(self):
        if self.request.method == "POST" or is_manager(
            self.request.user, self.get_school()
        ):
            return AdministrativeSummonSerializer
        return AdministrativeSummonTargetSerializer

    def perform_create(self, serializer):
        school = self.get_school()
        if not is_manager(self.request.user, school):
            raise PermissionDenied("إنشاء الاستدعاءات متاح للإدارة المخولة فقط.")
        serializer.save(school=school, issued_by=self.request.user)


class AdministrativeSummonDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "pk"

    def get_school(self):
        return get_school(self.request)

    def get_serializer_class(self):
        return (
            AdministrativeSummonSerializer
            if is_manager(self.request.user, self.get_school())
            else AdministrativeSummonTargetSerializer
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def get_queryset(self):
        qs = AdministrativeSummon.objects.filter(
            school=self.get_school(), is_archived=False
        ).select_related("student", "target_user", "issued_by")
        if is_manager(self.request.user, self.get_school()):
            return qs
        return qs.filter(target_user=self.request.user)


class AdministrativeSummonAttendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        school = get_school(request)
        if not is_manager(request.user, school):
            raise PermissionDenied("تأكيد حضور المستدعى متاح للإدارة فقط.")
        serializer = SummonAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            summon = get_object_or_404(
                AdministrativeSummon.objects.select_for_update(),
                pk=pk, school=school, is_archived=False,
            )
            if not summon.is_attended:
                summon.is_attended = True
                summon.attended_at = timezone.now()
                summon.session_minutes = serializer.validated_data.get(
                    "session_minutes", ""
                )
                summon.save(update_fields=[
                    "is_attended", "attended_at", "session_minutes", "updated_at"
                ])
        return Response(AdministrativeSummonSerializer(
            summon, context={"school": school}
        ).data)


class SchoolComplaintListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SchoolComplaintSerializer

    def get_school(self):
        return get_school(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def get_queryset(self):
        school = self.get_school()
        qs = SchoolComplaint.objects.filter(
            school=school, is_archived=False
        ).select_related("submitter", "resolved_by")
        if is_manager(self.request.user, school):
            return qs.order_by("-created_at")
        return qs.filter(submitter=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school(), submitter=self.request.user)


class SchoolComplaintDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SchoolComplaintSerializer
    lookup_url_kwarg = "pk"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = get_school(self.request)
        return context

    def get_queryset(self):
        school = get_school(self.request)
        qs = SchoolComplaint.objects.filter(
            school=school, is_archived=False
        ).select_related("submitter", "resolved_by")
        if is_manager(self.request.user, school):
            return qs
        return qs.filter(submitter=self.request.user)


class SchoolComplaintReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        school = get_school(request)
        if not is_manager(request.user, school):
            raise PermissionDenied("معالجة الشكاوى متاحة للإدارة المخولة فقط.")
        serializer = ComplaintReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            complaint = get_object_or_404(
                SchoolComplaint.objects.select_for_update(),
                pk=pk, school=school, is_archived=False,
            )
            allowed_transitions = {
                SchoolComplaint.Status.NEW: {
                    SchoolComplaint.Status.IN_REVIEW,
                },
                SchoolComplaint.Status.IN_REVIEW: {
                    SchoolComplaint.Status.RESOLVED,
                    SchoolComplaint.Status.CLOSED,
                },
                SchoolComplaint.Status.RESOLVED: {
                    SchoolComplaint.Status.CLOSED,
                },
            }
            new_status = serializer.validated_data["status"]
            if new_status not in allowed_transitions.get(complaint.status, set()):
                raise ValidationError("انتقال حالة الشكوى غير مسموح.")
            notes = serializer.validated_data.get("resolution_notes", "").strip()
            if new_status in {
                SchoolComplaint.Status.RESOLVED,
                SchoolComplaint.Status.CLOSED,
            } and not notes:
                raise ValidationError("أضف ملخص المعالجة قبل إغلاق الشكوى.")
            complaint.status = new_status
            complaint.resolution_notes = notes
            if new_status in {
                SchoolComplaint.Status.RESOLVED,
                SchoolComplaint.Status.CLOSED,
            }:
                complaint.resolved_by = request.user
                complaint.resolved_at = timezone.now()
            complaint.save(update_fields=[
                "status", "resolution_notes", "resolved_by", "resolved_at",
                "updated_at",
            ])
        return Response(SchoolComplaintSerializer(
            complaint, context={"school": school}
        ).data)
