from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.staff.api.serializers import (
    ApproveLeaveRequestSerializer,
    CreateLeaveRequestSerializer,
    LeaveRequestSerializer,
    LogAttendanceSerializer,
    StaffAttendanceSerializer,
    StaffMemberListSerializer,
)
from apps.staff.models import (
    LeaveRequest,
    LeaveType,
    StaffAttendance,
    StaffMember,
    Teacher,
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


class StaffMemberListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StaffMemberListSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        qs = StaffMember.objects.filter(school=school, is_archived=False).select_related("user")
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(user__first_name__icontains=search) | qs.filter(user__last_name__icontains=search) | qs.filter(job_title__icontains=search)
        return qs.order_by("role", "job_title")


class LeaveRequestListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        qs = LeaveRequest.objects.filter(school=school, is_archived=False).select_related(
            "teacher__user", "staff_member__user", "leave_type", "approved_by"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        serializer = LeaveRequestSerializer(qs.order_by("-created_at")[:100], many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        serializer = CreateLeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        leave_type = get_object_or_404(LeaveType, pk=data["leave_type_id"], school=school)
        teacher = None
        staff_member = None
        if data.get("teacher_id"):
            teacher = get_object_or_404(Teacher, pk=data["teacher_id"], school=school, is_archived=False)
        if data.get("staff_member_id"):
            staff_member = get_object_or_404(StaffMember, pk=data["staff_member_id"], school=school, is_archived=False)

        leave_req = LeaveRequest.objects.create(
            school=school,
            teacher=teacher,
            staff_member=staff_member,
            leave_type=leave_type,
            start_date=data["start_date"],
            end_date=data["end_date"],
            reason=data["reason"],
            status=LeaveRequest.Status.PENDING,
        )

        out_serializer = LeaveRequestSerializer(leave_req)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class LeaveRequestApproveRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        leave_req = get_object_or_404(LeaveRequest, pk=pk, school=school, is_archived=False)
        serializer = ApproveLeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        if action == "approve":
            leave_req.status = LeaveRequest.Status.APPROVED
            leave_req.approved_by = request.user
            leave_req.approved_at = timezone.now()
        else:
            leave_req.status = LeaveRequest.Status.REJECTED

        leave_req.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response({
            "message": f"تم تحديث حالة طلب الإجازة إلى {leave_req.get_status_display()}.",
            "status": leave_req.status,
        }, status=status.HTTP_200_OK)


class StaffAttendanceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        qs = StaffAttendance.objects.filter(school=school, is_archived=False).select_related(
            "teacher__user", "staff_member__user"
        )
        date_filter = request.query_params.get("date")
        if date_filter:
            qs = qs.filter(date=date_filter)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        serializer = StaffAttendanceSerializer(qs.order_by("-date")[:100], many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        serializer = LogAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        teacher = None
        staff_member = None
        if data.get("teacher_id"):
            teacher = get_object_or_404(Teacher, pk=data["teacher_id"], school=school, is_archived=False)
        if data.get("staff_member_id"):
            staff_member = get_object_or_404(StaffMember, pk=data["staff_member_id"], school=school, is_archived=False)

        att_date = data.get("date") or timezone.localdate()

        record, created = StaffAttendance.objects.update_or_create(
            school=school,
            teacher=teacher,
            staff_member=staff_member,
            date=att_date,
            is_archived=False,
            defaults={
                "status": data.get("status", StaffAttendance.Status.PRESENT),
                "time_in": data.get("time_in"),
                "time_out": data.get("time_out"),
                "delay_minutes": data.get("delay_minutes", 0),
                "notes": data.get("notes", ""),
            },
        )

        out_serializer = StaffAttendanceSerializer(record)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
