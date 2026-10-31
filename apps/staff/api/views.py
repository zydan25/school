from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import SchoolMembership
from rest_framework.exceptions import ValidationError

from apps.accounts.api_permissions import (
    HR_ROLES,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounts.services import is_platform_operator
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
    return resolve_active_school(request)


class StaffMemberListAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StaffMemberListSerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        permission = "staff.add_staffmember" if request.method == "POST" else "staff.view_staffmember"
        require_school_role_or_permission(request, self.get_school(), HR_ROLES, permission)

    def get_queryset(self):
        school = self.get_school()
        qs = StaffMember.objects.filter(
            school=school, is_archived=False,
        ).select_related("user")
        role = self.request.query_params.get("role")
        search = self.request.query_params.get("search")
        if role:
            qs = qs.filter(role=role)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(user__first_name__icontains=search)
                | Q(user__middle_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(employee_number__icontains=search)
                | Q(job_title__icontains=search)
            )
        return qs.order_by("role", "job_title")

    def perform_create(self, serializer):
        school = self.get_school()
        user = serializer.validated_data["user"]
        membership = user.school_memberships.filter(
            school=school, status=SchoolMembership.Status.ACTIVE,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).first()
        if membership is None:
            raise ValidationError("يجب أن يمتلك المستخدم عضوية مدرسة نشطة وسارية قبل إنشاء ملف موظف.")
        serializer.save(school=school)


class StaffMemberDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StaffMemberListSerializer
    lookup_url_kwarg = "pk"

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        permission_by_method = {
            "GET": "staff.view_staffmember",
            "PUT": "staff.change_staffmember",
            "PATCH": "staff.change_staffmember",
            "DELETE": "staff.delete_staffmember",
        }
        permission = permission_by_method.get(request.method, "staff.view_staffmember")
        require_school_role_or_permission(request, self.get_school(), HR_ROLES, permission)

    def get_queryset(self):
        return StaffMember.objects.filter(
            school=self.get_school(), is_archived=False,
        ).select_related("user")

    def perform_update(self, serializer):
        school = self.get_school()
        user = serializer.validated_data.get("user", serializer.instance.user)
        membership = user.school_memberships.filter(
            school=school, status=SchoolMembership.Status.ACTIVE,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).first()
        if membership is None:
            raise ValidationError("يجب أن يمتلك المستخدم عضوية مدرسة نشطة وسارية.")
        serializer.save()

    def perform_destroy(self, instance):
        instance.archive(actor=self.request.user, reason="أرشفة الموظف عبر API")


class LeaveRequestListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        qs = LeaveRequest.objects.filter(school=school, is_archived=False).select_related(
            "teacher__user", "staff_member__user", "leave_type", "approved_by"
        )
        can_manage = (
            has_school_roles(request.user, school, HR_ROLES)
            or is_platform_operator(request.user)
        )
        if not can_manage:
            own_teacher = Teacher.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).first()
            own_staff = StaffMember.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).first()
            if not own_teacher and not own_staff:
                raise PermissionDenied("لا تملك ملف موظف أو معلم في هذه المدرسة.")
            own_filter = Q(pk__in=[])
            if own_teacher:
                own_filter |= Q(teacher=own_teacher)
            if own_staff:
                own_filter |= Q(staff_member=own_staff)
            qs = qs.filter(own_filter)
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
        can_manage = (
            has_school_roles(request.user, school, HR_ROLES)
            or is_platform_operator(request.user)
        )
        if not can_manage:
            own_teacher = Teacher.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).first()
            own_staff = StaffMember.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).first()
            is_own_teacher = bool(own_teacher and str(data.get("teacher_id")) == str(own_teacher.pk))
            is_own_staff = bool(own_staff and str(data.get("staff_member_id")) == str(own_staff.pk))
            if not (is_own_teacher or is_own_staff):
                raise PermissionDenied("يمكنك تقديم طلب إجازة لملفك الوظيفي فقط.")

        leave_type = get_object_or_404(LeaveType, pk=data["leave_type_id"], school=school, is_archived=False)
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
        require_school_role_or_permission(request, school, HR_ROLES, "staff.change_leaverequest")
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
        can_manage = (
            has_school_roles(request.user, school, HR_ROLES)
            or is_platform_operator(request.user)
        )
        if not can_manage:
            own_teacher = Teacher.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).first()
            own_staff = StaffMember.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).first()
            if not own_teacher and not own_staff:
                raise PermissionDenied("لا تملك ملف موظف أو معلم في هذه المدرسة.")
            own_filter = Q(pk__in=[])
            if own_teacher:
                own_filter |= Q(teacher=own_teacher)
            if own_staff:
                own_filter |= Q(staff_member=own_staff)
            qs = qs.filter(own_filter)
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
        require_school_role_or_permission(
            request, school, HR_ROLES, "staff.add_staffattendance",
        )
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
