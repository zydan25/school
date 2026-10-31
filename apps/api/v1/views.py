"""Versioned REST API surface for the multi-role School mobile application."""
from __future__ import annotations

import os
from decimal import Decimal
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES, HR_ROLES, STUDENT_AFFAIRS_ROLES,
    has_school_roles, require_school_role_or_permission, resolve_active_school,
)
from apps.accounts.models import (
    MembershipRole, SchoolInvitation, SchoolMembership, SchoolRole, User,
)
from apps.accounts.services import (
    accept_school_invitation, active_membership, issue_school_invitation,
)
from apps.academics.models import (
    AcademicTerm, AcademicYear, Classroom, EducationalStage, GradeLevel,
    PeriodDefinition, SchoolWorkingDay, Section, Subject,
)
from apps.accounting.models import (
    Account, CostCenter, ExpenseCategory, FiscalPeriod, FiscalYear,
    JournalEntry, JournalEntryLine, PaymentVoucher, ReceiptVoucher,
)
from apps.accounting.services.auto_posting import reverse_journal_entry
from apps.assets.models import AssetCategory, AssetDepreciationEntry, FixedAsset
from apps.assessments.models import (
    AssessmentType, ExamCommittee, ExamSeating, GradeBook, OnlineExam,
    QuestionBank, StudentOnlineExamSubmission,
)
from apps.assignments.models import Homework, HomeworkSubmission
from apps.inventory.models import (
    InventoryItem, PurchaseOrder, PurchaseOrderItem, StockMovement,
    Supplier, VendorInvoice, Warehouse,
)
from apps.notifications.models import (
    ConversationMessage, ConversationParticipant, Notification,
    NotificationPreference, PushDevice, SchoolConversation,
)
from apps.staff.models import (
    Department, LeaveRequest, LeaveType, StaffAttendance, StaffMember,
    Teacher, TeacherAssignment, WorkShift,
)
from apps.students.models import (
    Guardian, Student, StudentGuardianRelation,
)
from apps.timetable.models import (
    ClassSchedule, DailyLessonLog, SchedulePeriodTemplate, SchoolBellSchedule,
)

from apps.api.v1.serializers import (
    AcademicTermSerializer, AcademicYearSerializer, AccountSerializer,
    AssetCategorySerializer, AssetDepreciationSerializer, AssessmentTypeSerializer,
    ClassroomSerializer, ClassScheduleSerializer, ConversationCreateSerializer,
    ConversationMessageSerializer,
    CostCenterSerializer, DailyLessonLogSerializer, DepartmentSerializer,
    EducationalStageSerializer, ExamCommitteeSerializer, ExamPaperQuestionSerializer,
    ExamSeatingSerializer, ExamSubmissionReviewSerializer,
    ExpenseCategorySerializer, FiscalPeriodSerializer, FiscalYearSerializer,
    FixedAssetSerializer, GradeBookSerializer, GradeLevelSerializer,
    GuardianSerializer, HomeworkSerializer, HomeworkSubmissionSerializer,
    InvitationSerializer, InventoryItemSerializer, JournalEntryCreateSerializer,
    JournalEntrySerializer, LeaveTypeSerializer,
    MembershipRoleSerializer, MembershipSerializer, MessageCreateSerializer,
    NotificationPreferenceSerializer, OnlineExamSerializer, PaymentVoucherSerializer,
    PeriodDefinitionSerializer, PushDeviceSerializer, PurchaseOrderItemSerializer,
    PurchaseOrderSerializer, QuestionBankTeacherSerializer, ReceiptVoucherSerializer,
    SchoolBellScheduleSerializer, SchoolConversationSerializer, SchoolRoleSerializer,
    SchoolWorkingDaySerializer, SchedulePeriodTemplateSerializer, SectionSerializer,
    StaffMemberSerializer, StockMovementSerializer, StudentEnrollmentSerializer,
    StudentGuardianRelationSerializer, StudentSerializer, SubjectSerializer,
    SupplierSerializer, TeacherAssignmentSerializer, TeacherSerializer,
    VendorInvoiceSerializer, WarehouseSerializer, WorkShiftSerializer,
)

ADMIN_ROLES = {
    "school-director", "school_director", "school-admin", "school_admin",
    "principal", "school-principal", "academic-coordinator", "academic_coordinator",
    "student-affairs", "student_affairs",
}
ACADEMIC_ADMIN_ROLES = ADMIN_ROLES | {"academic-head", "academic_head", "exam-controller", "exam_controller"}
READ_ROLES = ADMIN_ROLES | {
    "teacher", "guardian", "student", "hr-manager", "hr_manager",
    "accountant", "school-accountant", "school_accountant", "librarian",
}
TEACHER_ROLES = ADMIN_ROLES | {"teacher"}
HR_ADMIN_ROLES = ADMIN_ROLES | {"hr", "hr-manager", "hr_manager", "hr-specialist", "hr_specialist"}
INVENTORY_ROLES = ADMIN_ROLES | {"store-keeper", "store_keeper", "inventory-manager", "inventory_manager"}
GATE_ROLES = ADMIN_ROLES | {"gate-security", "gate_security", "school-gate-guard"}


def school_for(request):
    school = resolve_active_school(request)
    if not school:
        raise PermissionDenied("حدد المدرسة النشطة أولاً، وتأكد من أن عضويتك سارية.")
    return school


def is_admin(user, school, roles=ADMIN_ROLES):
    return has_school_roles(user, school, roles)


def user_student_profiles(user, school):
    return Student.objects.filter(user=user, school=school, is_archived=False)


def user_guardian_profiles(user, school):
    return Guardian.objects.filter(user=user, school=school, is_archived=False)


def user_teacher_profiles(user, school):
    return Teacher.objects.filter(user=user, school=school, is_archived=False)


def user_staff_profiles(user, school):
    return StaffMember.objects.filter(user=user, school=school, is_archived=False)


class TenantModelViewSet(viewsets.ModelViewSet):
    """Default-deny-by-role tenant CRUD; DELETE archives instead of destroying history."""
    permission_classes = [IsAuthenticated]
    read_roles = READ_ROLES
    write_roles = ADMIN_ROLES
    action_role_map = {}

    def get_school(self):
        return school_for(self.request)

    def get_queryset(self):
        model = self.serializer_class.Meta.model
        qs = model.objects.filter(school=self.get_school())
        if any(field.name == "is_archived" for field in model._meta.fields):
            qs = qs.filter(is_archived=False)
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = self.get_school()
        allowed = self.action_role_map.get(
            getattr(self, "action", ""),
            self.read_roles if getattr(self, "action", "") in {"list", "retrieve"} else self.write_roles,
        )
        require_school_role_or_permission(request, school, allowed)

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())

    def perform_destroy(self, instance):
        if hasattr(instance, "archive"):
            instance.archive(actor=self.request.user, reason="أرشفة عبر API")
        else:
            raise MethodNotAllowed("DELETE", detail="هذا المورد لا يدعم الأرشفة.")


# ---------------------------------------------------------------------------
# Identity, profile, memberships, school roles and invitations
# ---------------------------------------------------------------------------
class MyProfilesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = school_for(request)
        return Response({
            "teachers": [
                {"id": str(x.pk), "employee_number": x.employee_number, "specialization": x.specialization}
                for x in user_teacher_profiles(request.user, school)
            ],
            "guardians": [
                {"id": str(x.pk), "relationship_type": x.relationship_type, "children_count": x.children.filter(is_archived=False).count()}
                for x in user_guardian_profiles(request.user, school)
            ],
            "students": [
                {"id": str(x.pk), "student_id_number": x.student_id_number, "full_name": x.get_full_name(), "section_id": str(x.section_id)}
                for x in user_student_profiles(request.user, school)
            ],
            "staff": [
                {"id": str(x.pk), "employee_number": x.employee_number, "job_title": x.job_title, "role": x.role}
                for x in user_staff_profiles(request.user, school)
            ],
        })


class MembershipViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MembershipSerializer

    def get_school(self):
        return school_for(self.request)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_school_role_or_permission(request, self.get_school(), ADMIN_ROLES)

    def get_queryset(self):
        return SchoolMembership.objects.filter(
            school=self.get_school(),
        ).select_related("school", "user").prefetch_related("role_assignments__role").order_by("user__first_name")


class SchoolRoleViewSet(TenantModelViewSet):
    serializer_class = SchoolRoleSerializer
    read_roles = ADMIN_ROLES
    write_roles = ADMIN_ROLES
    action_role_map = {"list": ADMIN_ROLES, "retrieve": ADMIN_ROLES}

    def get_queryset(self):
        return SchoolRole.objects.filter(school=self.get_school(), is_archived=False).order_by("name")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school(), is_system=False)


class MembershipRoleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MembershipRoleSerializer

    def get_school(self):
        return school_for(self.request)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_school_role_or_permission(request, self.get_school(), ADMIN_ROLES)

    def get_queryset(self):
        return MembershipRole.objects.filter(
            membership__school=self.get_school(),
        ).select_related("membership__user", "role")

    def perform_create(self, serializer):
        school = self.get_school()
        membership = get_object_or_404(SchoolMembership, pk=serializer.validated_data["membership"].pk, school=school)
        role = get_object_or_404(SchoolRole, pk=serializer.validated_data["role"].pk, school=school, is_active=True, is_archived=False)
        assignment = MembershipRole(
            membership=membership, role=role, assigned_by=self.request.user,
            valid_from=serializer.validated_data.get("valid_from") or timezone.localdate(),
            valid_until=serializer.validated_data.get("valid_until"),
        )
        assignment.save()
        serializer.instance = assignment

    def perform_update(self, serializer):
        school = self.get_school()
        membership = get_object_or_404(
            SchoolMembership, pk=serializer.validated_data.get(
                "membership", serializer.instance.membership,
            ).pk, school=school,
        )
        role = get_object_or_404(
            SchoolRole,
            pk=serializer.validated_data.get("role", serializer.instance.role).pk,
            school=school, is_active=True, is_archived=False,
        )
        assignment = serializer.instance
        assignment.membership = membership
        assignment.role = role
        assignment.valid_from = serializer.validated_data.get("valid_from", assignment.valid_from)
        assignment.valid_until = serializer.validated_data.get("valid_until", assignment.valid_until)
        assignment.save()
        serializer.instance = assignment


class SchoolInvitationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = school_for(request)
        require_school_role_or_permission(request, school, ADMIN_ROLES)
        qs = SchoolInvitation.objects.filter(school=school).prefetch_related("roles").order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(InvitationSerializer(qs[:100], many=True).data)

    def post(self, request):
        school = school_for(request)
        require_school_role_or_permission(request, school, ADMIN_ROLES)
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone") or "").strip()
        role_ids = request.data.get("role_ids") or []
        if not isinstance(role_ids, list):
            raise ValidationError({"role_ids": "يجب إرسال الأدوار كمصفوفة من المعرفات."})
        if len(set(map(str, role_ids))) != len(role_ids):
            raise ValidationError({"role_ids": "لا تكرر الدور نفسه في الدعوة."})
        if not email:
            raise ValidationError({"email": "البريد الإلكتروني مطلوب لإرسال الدعوة."})
        roles = list(SchoolRole.objects.filter(
            school=school, pk__in=role_ids, is_active=True, is_archived=False,
        ))
        if len(roles) != len(set(role_ids)):
            raise ValidationError({"role_ids": "تتضمن القائمة دوراً غير موجود أو تابعاً لمدرسة أخرى."})
        expires_at = request.data.get("expires_at")
        if expires_at:
            try:
                expires_at = timezone.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                raise ValidationError({"expires_at": "أدخل تاريخاً ووقتاً بصيغة ISO-8601."})
        else:
            expires_at = timezone.now() + timedelta(days=7)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        if expires_at <= timezone.now():
            raise ValidationError({"expires_at": "يجب أن يكون انتهاء الدعوة في المستقبل."})
        invitation, raw_token = issue_school_invitation(
            school=school, invited_by=request.user, email=email,
            phone=phone, expires_at=expires_at, roles=roles,
            message=request.data.get("message", ""),
        )
        data = InvitationSerializer(invitation).data
        # Token is returned exactly once; store only its hash in the database.
        data["acceptance_token"] = raw_token
        data["delivery_required"] = True
        return Response(data, status=status.HTTP_201_CREATED)


    def revoke(self, request, invitation_id):
        school = school_for(request)
        require_school_role_or_permission(request, school, ADMIN_ROLES)
        with transaction.atomic():
            invitation = get_object_or_404(
                SchoolInvitation.objects.select_for_update(),
                pk=invitation_id, school=school,
            )
            if invitation.status != SchoolInvitation.Status.PENDING:
                raise ValidationError("لا يمكن إلغاء دعوة لم تعد معلقة.")
            invitation.status = SchoolInvitation.Status.REVOKED
            invitation.save(update_fields=["status", "updated_at"])
        return Response({"id": str(invitation.pk), "status": invitation.status})


class RevokeInvitationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invitation_id):
        school = school_for(request)
        require_school_role_or_permission(request, school, ADMIN_ROLES)
        with transaction.atomic():
            invitation = get_object_or_404(
                SchoolInvitation.objects.select_for_update(),
                pk=invitation_id, school=school,
            )
            if invitation.status != SchoolInvitation.Status.PENDING:
                raise ValidationError("لا يمكن إلغاء دعوة لم تعد معلقة.")
            invitation.status = SchoolInvitation.Status.REVOKED
            invitation.save(update_fields=["status", "updated_at"])
        return Response({"id": str(invitation.pk), "status": invitation.status})


class AcceptInvitationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        if not token:
            raise ValidationError({"token": "رمز الدعوة مطلوب."})
        membership = accept_school_invitation(raw_token=token, user=request.user)
        return Response({
            "membership_id": str(membership.pk),
            "school": {"id": str(membership.school_id), "code": membership.school.code, "name": membership.school.name},
            "roles": sorted(membership.get_role_codes()),
            "status": membership.status,
        })


class GuardianChildrenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = school_for(request)
        guardian = user_guardian_profiles(request.user, school).first()
        if guardian:
            children = guardian.children.filter(school=school, is_archived=False).select_related("section", "grade_level")
            return Response({
                "guardian_id": str(guardian.pk),
                "results": [{
                    "id": str(x.pk), "student_id_number": x.student_id_number,
                    "name": x.get_full_name(), "grade": x.grade_level.name,
                    "section": x.section.name, "status": x.status,
                    "receives_notifications": x.guardians.filter(guardian=guardian, is_archived=False).values_list("receives_notifications", flat=True).first(),
                    "can_pickup": x.guardians.filter(guardian=guardian, is_archived=False).values_list("can_pickup", flat=True).first(),
                } for x in children],
            })
        if is_admin(request.user, school):
            guardian_id = request.query_params.get("guardian_id")
            qs = StudentGuardianRelation.objects.filter(school=school, is_archived=False).select_related("student", "guardian__user")
            if guardian_id:
                qs = qs.filter(guardian_id=guardian_id)
            return Response(StudentGuardianRelationSerializer(qs[:200], many=True, context={"school": school}).data)
        raise PermissionDenied("الواجهة متاحة لولي الأمر المرتبط بأبناء أو لإدارة المدرسة.")


class GuardianProfileViewSet(TenantModelViewSet):
    serializer_class = GuardianSerializer
    read_roles = ADMIN_ROLES | {"guardian"}
    write_roles = STUDENT_AFFAIRS_ROLES

    def get_queryset(self):
        qs = Guardian.objects.filter(
            school=self.get_school(), is_archived=False,
        ).select_related("user").prefetch_related("children")
        if has_school_roles(self.request.user, self.get_school(), {"guardian"}) and not is_admin(self.request.user, self.get_school()):
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, STUDENT_AFFAIRS_ROLES,
            "students.add_guardian",
        )
        user = get_object_or_404(
            User, pk=self.request.data.get("user_id"), is_active=True,
        )
        if active_membership(user=user, school=school) is None:
            raise ValidationError("يجب أن يمتلك ولي الأمر عضوية نشطة في المدرسة أولاً.")
        serializer.save(school=school, user=user)


class GuardianRelationViewSet(TenantModelViewSet):
    serializer_class = StudentGuardianRelationSerializer
    read_roles = ADMIN_ROLES
    write_roles = STUDENT_AFFAIRS_ROLES

    def get_queryset(self):
        return StudentGuardianRelation.objects.filter(
            school=self.get_school(), is_archived=False,
        ).select_related("student", "guardian__user")


class AcademicYearViewSet(TenantModelViewSet):
    serializer_class = AcademicYearSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        return AcademicYear.objects.filter(school=self.get_school(), is_archived=False).order_by("-starts_on")


class AcademicTermViewSet(TenantModelViewSet):
    serializer_class = AcademicTermSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        return AcademicTerm.objects.filter(school=self.get_school(), is_archived=False).select_related("academic_year").order_by("academic_year__starts_on", "number")


class EducationalStageViewSet(TenantModelViewSet):
    serializer_class = EducationalStageSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class GradeLevelViewSet(TenantModelViewSet):
    serializer_class = GradeLevelSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("stage")
        stage_id = self.request.query_params.get("stage_id")
        return qs.filter(stage_id=stage_id) if stage_id else qs


class ClassroomViewSet(TenantModelViewSet):
    serializer_class = ClassroomSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class SectionViewSet(TenantModelViewSet):
    serializer_class = SectionSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("academic_year", "grade", "homeroom_classroom")
        year_id = self.request.query_params.get("academic_year_id")
        grade_id = self.request.query_params.get("grade_id")
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        if grade_id:
            qs = qs.filter(grade_id=grade_id)
        return qs


class SubjectViewSet(TenantModelViewSet):
    serializer_class = SubjectSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class PeriodDefinitionViewSet(TenantModelViewSet):
    serializer_class = PeriodDefinitionSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class SchoolWorkingDayViewSet(TenantModelViewSet):
    serializer_class = SchoolWorkingDaySerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class TeacherViewSet(TenantModelViewSet):
    serializer_class = TeacherSerializer
    read_roles = HR_ADMIN_ROLES | {"teacher"}
    write_roles = HR_ADMIN_ROLES

    def get_queryset(self):
        qs = Teacher.objects.filter(school=self.get_school(), is_archived=False).select_related("user")
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school(), HR_ADMIN_ROLES):
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        require_school_role_or_permission(self.request, self.get_school(), HR_ADMIN_ROLES, "staff.add_teacher")
        user = get_object_or_404(User, pk=self.request.data.get("user_id"), is_active=True)
        if active_membership(user=user, school=self.get_school()) is None:
            raise ValidationError("يجب إنشاء عضوية المدرسة للمستخدم قبل إنشاء ملف المعلم.")
        serializer.save(school=self.get_school(), user=user)


class TeacherAssignmentViewSet(TenantModelViewSet):
    serializer_class = TeacherAssignmentSerializer
    read_roles = HR_ADMIN_ROLES | ACADEMIC_ADMIN_ROLES | {"teacher"}
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = TeacherAssignment.objects.filter(school=self.get_school(), is_archived=False).select_related("teacher__user", "subject", "section", "academic_year")
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school()):
            teacher = user_teacher_profiles(self.request.user, self.get_school()).first()
            qs = qs.filter(teacher=teacher) if teacher else qs.none()
        year_id = self.request.query_params.get("academic_year_id")
        return qs.filter(academic_year_id=year_id) if year_id else qs


class DepartmentViewSet(TenantModelViewSet):
    serializer_class = DepartmentSerializer
    read_roles = HR_ADMIN_ROLES
    write_roles = HR_ADMIN_ROLES


class WorkShiftViewSet(TenantModelViewSet):
    serializer_class = WorkShiftSerializer
    read_roles = HR_ADMIN_ROLES
    write_roles = HR_ADMIN_ROLES


class LeaveTypeViewSet(TenantModelViewSet):
    serializer_class = LeaveTypeSerializer
    read_roles = HR_ADMIN_ROLES
    write_roles = HR_ADMIN_ROLES


# ---------------------------------------------------------------------------
# Homework, assessment and online exam workflows
# ---------------------------------------------------------------------------
class HomeworkViewSet(TenantModelViewSet):
    serializer_class = HomeworkSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student", "guardian"}
    write_roles = TEACHER_ROLES
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "retrieve": ADMIN_ROLES | {"teacher", "student", "guardian"},
    }

    def get_queryset(self):
        school = self.get_school()
        qs = Homework.objects.filter(
            school=school, is_archived=False, is_active=True,
        ).select_related("subject", "section", "teacher__user")
        if not is_admin(self.request.user, school):
            allowed = Q(pk__in=[])
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).first()
                if teacher:
                    allowed |= Q(teacher=teacher)
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if student:
                    allowed |= Q(section_id=student.section_id)
            if has_school_roles(self.request.user, school, {"guardian"}):
                guardian = user_guardian_profiles(self.request.user, school).first()
                if guardian:
                    sections = guardian.children.filter(
                        school=school, is_archived=False,
                    ).values_list("section_id", flat=True)
                    allowed |= Q(section_id__in=sections)
            qs = qs.filter(allowed)
        section_id = self.request.query_params.get("section_id")
        subject_id = self.request.query_params.get("subject_id")
        if section_id:
            qs = qs.filter(section_id=section_id)
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        return qs.order_by("-assigned_date", "-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).first()
        requested_teacher_id = self.request.data.get("teacher_id")
        if is_admin(self.request.user, school) and requested_teacher_id:
            teacher = get_object_or_404(
                Teacher, pk=requested_teacher_id, school=school,
                is_archived=False, is_active_teaching=True,
            )
        elif not teacher:
            raise PermissionDenied("يجب ربط حسابك بملف معلم قبل إنشاء واجب.")
        section = serializer.validated_data["section"]
        subject = serializer.validated_data["subject"]
        if teacher and not is_admin(self.request.user, school):
            assigned = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, section=section, subject=subject,
                academic_year=section.academic_year, is_archived=False,
            ).exists()
            if not assigned:
                raise PermissionDenied("لا يمكنك إسناد واجب لمادة أو شعبة غير مسندة إليك.")
        serializer.save(school=school, teacher=teacher)


class HomeworkSubmissionViewSet(TenantModelViewSet):
    serializer_class = HomeworkSubmissionSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student", "guardian"}
    write_roles = {"student", "teacher"} | ADMIN_ROLES
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "retrieve": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "submit": {"student"} | ADMIN_ROLES,
        "grade": TEACHER_ROLES,
    }

    def get_queryset(self):
        school = self.get_school()
        qs = HomeworkSubmission.objects.filter(
            school=school, is_archived=False,
        ).select_related("homework", "student", "graded_by")
        if not is_admin(self.request.user, school):
            allowed = Q(pk__in=[])
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if student:
                    allowed |= Q(student=student)
            if has_school_roles(self.request.user, school, {"guardian"}):
                guardian = user_guardian_profiles(self.request.user, school).first()
                if guardian:
                    allowed |= Q(student__in=guardian.children.filter(
                        school=school, is_archived=False,
                    ))
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).first()
                if teacher:
                    allowed |= Q(homework__teacher=teacher)
            qs = qs.filter(allowed)
        homework_id = self.request.query_params.get("homework_id")
        student_id = self.request.query_params.get("student_id")
        if homework_id:
            qs = qs.filter(homework_id=homework_id)
        if student_id and is_admin(self.request.user, school):
            qs = qs.filter(student_id=student_id)
        return qs.order_by("-submitted_at")

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "POST",
            detail="استخدم POST /homework-submissions/submit/ لإرسال واجب.",
        )

    @action(
        detail=False, methods=["post"], url_path="submit",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def submit(self, request):
        school = self.get_school()
        student = user_student_profiles(request.user, school).first()
        if not student or not has_school_roles(request.user, school, {"student"}):
            raise PermissionDenied("تسليم الواجب متاح لحساب الطالب المرتبط فقط.")
        homework = get_object_or_404(
            Homework, pk=request.data.get("homework_id"), school=school,
            is_archived=False, is_active=True,
        )
        if homework.section_id != student.section_id:
            raise PermissionDenied("الواجب لا يخص الشعبة الحالية للطالب.")
        attachment = request.FILES.get("attachment")
        if attachment:
            extension = os.path.splitext(attachment.name)[1].lower()
            if extension not in {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}:
                raise ValidationError({"attachment": "نوع الملف غير مدعوم."})
            if attachment.size > 15 * 1024 * 1024:
                raise ValidationError({"attachment": "الحد الأقصى لحجم المرفق 15 ميجابايت."})
        late = timezone.now() > homework.due_date
        with transaction.atomic():
            existing = HomeworkSubmission.objects.select_for_update().filter(
                school=school, homework=homework, student=student,
                is_archived=False,
            ).first()
            created = existing is None
            if existing and existing.status == HomeworkSubmission.Status.GRADED:
                raise ValidationError("تم تصحيح هذا الواجب ولا يمكن استبدال التسليم.")
            if created:
                existing = HomeworkSubmission(
                    school=school, homework=homework, student=student,
                )
            existing.submission_text = request.data.get("submission_text", "")
            if attachment:
                existing.attachment = attachment
            existing.status = (
                HomeworkSubmission.Status.LATE
                if late else HomeworkSubmission.Status.SUBMITTED
            )
            existing.submitted_at = timezone.now()
            existing.save()
        return Response(
            self.get_serializer(existing).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="grade")
    def grade(self, request, pk=None):
        school = self.get_school()
        submission = self.get_object()
        require_school_role_or_permission(request, school, TEACHER_ROLES)
        teacher = user_teacher_profiles(request.user, school).first()
        if not is_admin(request.user, school):
            if not teacher or submission.homework.teacher_id != teacher.pk:
                raise PermissionDenied("لا يمكنك تصحيح تسليم واجب لمعلم آخر.")
        try:
            score = Decimal(str(request.data.get("score")))
        except Exception:
            raise ValidationError({"score": "الدرجة المدخلة غير صحيحة."})
        if score < 0 or score > submission.homework.max_score:
            raise ValidationError({
                "score": f"الدرجة يجب أن تكون بين صفر و {submission.homework.max_score}.",
            })
        submission.score = score
        submission.teacher_feedback = request.data.get("teacher_feedback", "")
        submission.graded_by = teacher
        submission.graded_at = timezone.now()
        submission.status = HomeworkSubmission.Status.GRADED
        submission.save(update_fields=[
            "score", "teacher_feedback", "graded_by", "graded_at",
            "status", "updated_at",
        ])
        return Response(self.get_serializer(submission).data)


class AssessmentTypeViewSet(TenantModelViewSet):
    serializer_class = AssessmentTypeSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class GradeBookViewSet(TenantModelViewSet):
    serializer_class = GradeBookSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student", "guardian"}
    write_roles = TEACHER_ROLES
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "retrieve": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "publish": ACADEMIC_ADMIN_ROLES,
    }

    def get_queryset(self):
        school = self.get_school()
        qs = GradeBook.objects.filter(
            school=school, is_archived=False,
        ).select_related("student", "subject", "academic_term", "assessment_type", "graded_by")
        if not is_admin(self.request.user, school):
            allowed = Q(pk__in=[])
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if student:
                    allowed |= Q(student=student, is_published=True)
            if has_school_roles(self.request.user, school, {"guardian"}):
                guardian = user_guardian_profiles(self.request.user, school).first()
                if guardian:
                    allowed |= Q(
                        student__in=guardian.children.filter(
                            school=school, is_archived=False,
                        ),
                        is_published=True,
                    )
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).first()
                if teacher:
                    sections = teacher.assignments.filter(
                        is_archived=False,
                    ).values_list("section_id", flat=True)
                    allowed |= Q(student__section_id__in=sections)
            qs = qs.filter(allowed)
        term_id = self.request.query_params.get("academic_term_id")
        student_id = self.request.query_params.get("student_id")
        if term_id:
            qs = qs.filter(academic_term_id=term_id)
        if student_id and is_admin(self.request.user, school):
            qs = qs.filter(student_id=student_id)
        return qs.order_by("-graded_at")

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).first()
        data = serializer.validated_data
        academic_year = (
            data["academic_term"].academic_year
            if data.get("academic_term") else data["student"].academic_year
        )
        if teacher and not is_admin(self.request.user, school):
            assignment = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, subject=data["subject"],
                section=data["student"].section, academic_year=academic_year,
                is_archived=False,
            ).exists()
            if not assignment:
                raise PermissionDenied("المادة أو شعبة الطالب غير مسندة إليك.")
        serializer.save(school=school, graded_by=teacher, graded_at=timezone.now())

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        entry = self.get_object()
        entry.is_published = bool(request.data.get("is_published", True))
        entry.save(update_fields=["is_published", "updated_at"])
        return Response({"id": str(entry.pk), "is_published": entry.is_published})


class QuestionBankViewSet(TenantModelViewSet):
    serializer_class = QuestionBankTeacherSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}
    write_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}

    def get_queryset(self):
        qs = QuestionBank.objects.filter(
            school=self.get_school(), is_archived=False,
        ).select_related("subject", "grade_level", "created_by")
        subject_id = self.request.query_params.get("subject_id")
        grade_id = self.request.query_params.get("grade_level_id")
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).first()
        data = serializer.validated_data
        if teacher and not is_admin(self.request.user, school):
            assignments = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, subject=data["subject"],
                is_archived=False,
            )
            if data.get("grade_level"):
                assignments = assignments.filter(section__grade=data["grade_level"])
            if not assignments.exists():
                raise PermissionDenied("لا يمكنك إضافة سؤال لمادة أو صف غير مسند إليك.")
        serializer.save(school=school, created_by=self.request.user)


class OnlineExamViewSet(TenantModelViewSet):
    serializer_class = OnlineExamSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student"},
        "retrieve": ADMIN_ROLES | {"teacher", "student"},
        "paper": {"student"} | ADMIN_ROLES,
        "start": {"student"} | ADMIN_ROLES,
        "submit": {"student"} | ADMIN_ROLES,
    }

    def get_queryset(self):
        school = self.get_school()
        qs = OnlineExam.objects.filter(
            school=school, is_archived=False,
        ).select_related("subject", "academic_term", "grade_level", "section")
        if not is_admin(self.request.user, school):
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if not student:
                    return qs.none()
                qs = qs.filter(is_published=True).filter(
                    Q(section=student.section)
                    | Q(section__isnull=True, grade_level=student.grade_level)
                )
            elif has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).first()
                if not teacher:
                    return qs.none()
                assigned = teacher.assignments.filter(is_archived=False)
                sections = assigned.values_list("section_id", flat=True)
                grades = assigned.values_list("section__grade_id", flat=True)
                qs = qs.filter(
                    Q(created_by=self.request.user)
                    | Q(section_id__in=sections)
                    | Q(section__isnull=True, grade_level_id__in=grades)
                )
            else:
                return qs.none()
        return qs.order_by("-start_time")

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).first()
        data = serializer.validated_data
        section = data.get("section")
        academic_year = data["academic_term"].academic_year
        if section and (
            section.grade_id != data["grade_level"].pk
            or section.academic_year_id != academic_year.pk
        ):
            raise ValidationError("الشعبة يجب أن تتبع الصف والسنة الدراسية المحددين للاختبار.")
        if data["end_time"] <= data["start_time"]:
            raise ValidationError({"end_time": "وقت انتهاء الاختبار يجب أن يكون بعد بدايته."})
        if data["passing_marks"] > data["total_marks"]:
            raise ValidationError({"passing_marks": "درجة النجاح لا يمكن أن تتجاوز الدرجة العظمى."})
        questions = list(data.get("questions", []))
        question_total = sum((q.default_marks for q in questions), Decimal("0.00"))
        if question_total > data["total_marks"]:
            raise ValidationError({"questions": "مجموع درجات الأسئلة يتجاوز الدرجة العظمى للاختبار."})
        if teacher and not is_admin(self.request.user, school):
            assignments = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, subject=data["subject"],
                academic_year=academic_year, is_archived=False,
            )
            if section:
                assignments = assignments.filter(section=section)
            else:
                assignments = assignments.filter(section__grade=data["grade_level"])
            if not assignments.exists():
                raise PermissionDenied("لا يمكنك إنشاء اختبار لمادة أو صف غير مسند إليك.")
        serializer.save(school=school, created_by=self.request.user)

    def _student_can_take_exam(self, student, exam):
        if not student or not exam.is_published:
            return False
        if exam.section_id:
            return exam.section_id == student.section_id
        return exam.grade_level_id == student.grade_level_id

    @action(detail=True, methods=["get"], url_path="paper")
    def paper(self, request, pk=None):
        exam = self.get_object()
        student = user_student_profiles(request.user, self.get_school()).first()
        if not is_admin(request.user, self.get_school()):
            if not self._student_can_take_exam(student, exam):
                raise PermissionDenied("الاختبار غير متاح لهذا الطالب.")
            if timezone.now() < exam.start_time or timezone.now() > exam.end_time:
                raise ValidationError("الاختبار غير متاح حالياً خارج فترة أدائه.")
        questions = exam.questions.all()
        return Response({
            "exam": {
                "id": str(exam.pk), "title": exam.title,
                "duration_minutes": exam.duration_minutes,
                "start_time": exam.start_time, "end_time": exam.end_time,
                "total_marks": str(exam.total_marks),
                "instructions": exam.instructions,
            },
            "questions": ExamPaperQuestionSerializer(questions, many=True).data,
        })

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        exam = self.get_object()
        student = user_student_profiles(request.user, self.get_school()).first()
        if not self._student_can_take_exam(student, exam):
            raise PermissionDenied("هذا الاختبار غير متاح لحسابك.")
        now = timezone.now()
        if now < exam.start_time or now > exam.end_time:
            raise ValidationError("لا يمكن بدء الاختبار خارج الوقت المحدد.")
        submission, created = StudentOnlineExamSubmission.objects.get_or_create(
            school=self.get_school(), exam=exam, student=student,
            defaults={
                "started_at": now,
                "status": StudentOnlineExamSubmission.Status.IN_PROGRESS,
            },
        )
        if not created and submission.status != StudentOnlineExamSubmission.Status.IN_PROGRESS:
            raise ValidationError("سبق تسليم هذا الاختبار.")
        return Response({
            "submission_id": str(submission.pk),
            "started_at": submission.started_at,
            "status": submission.status,
            "deadline": min(
                exam.end_time,
                submission.started_at + timedelta(minutes=exam.duration_minutes),
            ),
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        exam = self.get_object()
        student = user_student_profiles(request.user, self.get_school()).first()
        if not self._student_can_take_exam(student, exam):
            raise PermissionDenied("تسليم الاختبار متاح للطالب المستهدف فقط.")
        answers = request.data.get("answers")
        if not isinstance(answers, dict):
            raise ValidationError({"answers": "أرسل الإجابات ككائن JSON: question_id -> answer."})
        allowed_questions = list(exam.questions.all())
        allowed_ids = {str(question.pk) for question in allowed_questions}
        if set(answers) - allowed_ids:
            raise ValidationError({"answers": "تتضمن الإجابات سؤالاً لا ينتمي لهذا الاختبار."})
        with transaction.atomic():
            submission = get_object_or_404(
                StudentOnlineExamSubmission.objects.select_for_update(),
                school=self.get_school(), exam=exam, student=student,
                is_archived=False,
            )
            if submission.status != StudentOnlineExamSubmission.Status.IN_PROGRESS:
                raise ValidationError("تم تسليم هذا الاختبار مسبقاً.")
            now = timezone.now()
            deadline = min(
                exam.end_time,
                submission.started_at + timedelta(minutes=exam.duration_minutes),
            )
            submission.submitted_at = min(now, deadline)
            submission.answers_json = answers
            submission.status = StudentOnlineExamSubmission.Status.SUBMITTED
            submission.auto_score = Decimal("0.00")
            for question in allowed_questions:
                if question.question_type in {"mcq", "true_false"}:
                    student_answer = str(answers.get(str(question.pk), "")).strip().lower()
                    correct_answer = str(question.correct_answer).strip().lower()
                    if student_answer and student_answer == correct_answer:
                        submission.auto_score += question.default_marks
            if submission.auto_score > exam.total_marks:
                raise ValidationError("مجموع درجات الأسئلة الموضوعية يتجاوز الدرجة العظمى للاختبار.")
            submission.final_score = submission.auto_score
            submission.save(update_fields=[
                "answers_json", "submitted_at", "status",
                "auto_score", "final_score", "updated_at",
            ])
        return Response({
            "submission_id": str(submission.pk),
            "status": submission.status,
            "submitted_at": submission.submitted_at,
            "auto_score": str(submission.auto_score),
        })


class ExamSubmissionViewSet(TenantModelViewSet):
    serializer_class = ExamSubmissionReviewSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES
    action_role_map = {
        "list": ACADEMIC_ADMIN_ROLES | {"teacher", "student"},
        "retrieve": ACADEMIC_ADMIN_ROLES | {"teacher", "student"},
        "grade": ACADEMIC_ADMIN_ROLES | {"teacher"},
    }

    def get_queryset(self):
        school = self.get_school()
        qs = StudentOnlineExamSubmission.objects.filter(
            school=school, is_archived=False,
        ).select_related("exam", "student", "graded_by")
        if not is_admin(self.request.user, school):
            allowed = Q(pk__in=[])
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if student:
                    allowed |= Q(student=student)
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).first()
                if teacher:
                    assigned = teacher.assignments.filter(is_archived=False)
                    allowed |= Q(exam__section_id__in=assigned.values_list("section_id", flat=True))
                    allowed |= Q(
                        exam__section__isnull=True,
                        exam__grade_level_id__in=assigned.values_list("section__grade_id", flat=True),
                    )
            qs = qs.filter(allowed)
        return qs.order_by("-submitted_at")

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="تنشأ محاولة الاختبار من خلال POST /online-exams/{id}/start/.")

    @action(detail=True, methods=["post"], url_path="grade")
    def grade(self, request, pk=None):
        school = self.get_school()
        with transaction.atomic():
            submission = get_object_or_404(
                StudentOnlineExamSubmission.objects.select_for_update().select_related("exam"),
                pk=pk, school=school, is_archived=False,
            )
            teacher = user_teacher_profiles(request.user, school).first()
            if not is_admin(request.user, school):
                if not teacher:
                    raise PermissionDenied("يجب ربط حسابك بملف معلم.")
                assigned = teacher.assignments.filter(
                    subject=submission.exam.subject, is_archived=False,
                )
                if submission.exam.section_id:
                    assigned = assigned.filter(section_id=submission.exam.section_id)
                else:
                    assigned = assigned.filter(section__grade_id=submission.exam.grade_level_id)
                if not assigned.exists():
                    raise PermissionDenied("لا يمكنك تصحيح اختبار غير مسند إليك.")
            if submission.status not in {
                StudentOnlineExamSubmission.Status.SUBMITTED,
                StudentOnlineExamSubmission.Status.GRADED,
            }:
                raise ValidationError("لا يمكن تصحيح محاولة لم تُسلّم بعد.")
            try:
                manual_score = Decimal(str(request.data.get("manual_score", "0")))
            except Exception:
                raise ValidationError({"manual_score": "الدرجة المقالية غير صحيحة."})
            if (
                manual_score < 0
                or submission.auto_score + manual_score > submission.exam.total_marks
            ):
                raise ValidationError({
                    "manual_score": "إجمالي الدرجة يتجاوز الدرجة العظمى للاختبار أو أقل من الصفر.",
                })
            submission.manual_score = manual_score
            submission.final_score = submission.auto_score + manual_score
            submission.teacher_feedback = request.data.get("teacher_feedback", "")
            submission.graded_by = request.user
            submission.status = StudentOnlineExamSubmission.Status.GRADED
            submission.save(update_fields=[
                "manual_score", "final_score", "teacher_feedback",
                "graded_by", "status", "updated_at",
            ])
        return Response({
            "id": str(submission.pk), "status": submission.status,
            "auto_score": str(submission.auto_score),
            "manual_score": str(submission.manual_score),
            "final_score": str(submission.final_score),
        })


class ExamCommitteeViewSet(TenantModelViewSet):
    serializer_class = ExamCommitteeSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES


class ExamSeatingViewSet(TenantModelViewSet):
    serializer_class = ExamSeatingSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("student", "committee", "academic_year")
        if has_school_roles(self.request.user, self.get_school(), {"student"}) and not is_admin(self.request.user, self.get_school()):
            student = user_student_profiles(self.request.user, self.get_school()).first()
            qs = qs.filter(student=student) if student else qs.none()
        return qs


# ---------------------------------------------------------------------------
# Weekly timetable, personal timetable and lesson logs
# ---------------------------------------------------------------------------
class SchoolBellScheduleViewSet(TenantModelViewSet):
    serializer_class = SchoolBellScheduleSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class SchedulePeriodTemplateViewSet(TenantModelViewSet):
    serializer_class = SchedulePeriodTemplateSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("schedule")
        schedule_id = self.request.query_params.get("schedule_id")
        return qs.filter(schedule_id=schedule_id) if schedule_id else qs


class ClassScheduleViewSet(TenantModelViewSet):
    serializer_class = ClassScheduleSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("section", "subject", "teacher__user", "classroom", "academic_year")
        year = self.request.query_params.get("academic_year_id")
        section = self.request.query_params.get("section_id")
        teacher = self.request.query_params.get("teacher_id")
        day = self.request.query_params.get("day_of_week")
        if year:
            qs = qs.filter(academic_year_id=year)
        if section:
            qs = qs.filter(section_id=section)
        if teacher:
            qs = qs.filter(teacher_id=teacher)
        if day:
            qs = qs.filter(day_of_week=day)
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school()):
            profile = user_teacher_profiles(self.request.user, self.get_school()).first()
            qs = qs.filter(teacher=profile) if profile else qs.none()
        return qs.order_by("day_of_week", "period_number")


class DailyLessonLogViewSet(TenantModelViewSet):
    serializer_class = DailyLessonLogSerializer
    read_roles = READ_ROLES
    write_roles = TEACHER_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("schedule", "schedule__section", "schedule__subject")
        date_filter = self.request.query_params.get("date")
        section_id = self.request.query_params.get("section_id")
        if date_filter:
            qs = qs.filter(date=date_filter)
        if section_id:
            qs = qs.filter(schedule__section_id=section_id)
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school()):
            teacher = user_teacher_profiles(self.request.user, self.get_school()).first()
            qs = qs.filter(schedule__teacher=teacher) if teacher else qs.none()
        return qs

    def perform_create(self, serializer):
        teacher = user_teacher_profiles(self.request.user, self.get_school()).first()
        schedule = serializer.validated_data["schedule"]
        if teacher and not is_admin(self.request.user, self.get_school()) and schedule.teacher_id != teacher.pk:
            raise PermissionDenied("لا يمكنك توثيق تنفيذ حصة لمعلم آخر.")
        serializer.save(school=self.get_school())


class MyWeeklyTimetableAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = school_for(request)
        student = user_student_profiles(request.user, school).first()
        teacher = user_teacher_profiles(request.user, school).first()
        section_id = request.query_params.get("section_id")
        qs = ClassSchedule.objects.filter(school=school, is_archived=False).select_related(
            "section", "subject", "teacher__user", "classroom", "bell_schedule"
        )
        if teacher and not is_admin(request.user, school):
            qs = qs.filter(teacher=teacher)
        elif student:
            qs = qs.filter(section_id=student.section_id)
        elif has_school_roles(request.user, school, {"guardian"}):
            guardian = user_guardian_profiles(request.user, school).first()
            children = guardian.children.filter(is_archived=False) if guardian else Student.objects.none()
            if section_id and (not children.filter(section_id=section_id).exists()):
                raise PermissionDenied("الشعبة المحددة لا تخص أحد الأبناء المرتبطين بحسابك.")
            qs = qs.filter(section__in=children.values("section_id"))
        elif is_admin(request.user, school):
            if section_id:
                qs = qs.filter(section_id=section_id)
        else:
            raise PermissionDenied("لا يوجد ملف طالب أو معلم مرتبط بحسابك.")
        return Response([{
            "id": str(x.pk), "day_of_week": x.day_of_week,
            "period_number": x.period_number, "start_time": x.start_time,
            "end_time": x.end_time, "subject": x.subject.name,
            "section": x.section.name, "section_id": str(x.section_id),
            "teacher": x.teacher.user.get_full_name(), "classroom": x.classroom.name if x.classroom_id else None,
        } for x in qs.order_by("day_of_week", "period_number")])


# ---------------------------------------------------------------------------
# Accounting: chart, fiscal periods, journals and double-entry vouchers
# ---------------------------------------------------------------------------
class FiscalYearViewSet(TenantModelViewSet):
    serializer_class = FiscalYearSerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES


class FiscalPeriodViewSet(TenantModelViewSet):
    serializer_class = FiscalPeriodSerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("fiscal_year")
        year_id = self.request.query_params.get("fiscal_year_id")
        return qs.filter(fiscal_year_id=year_id) if year_id else qs


class AccountViewSet(TenantModelViewSet):
    serializer_class = AccountSerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("parent").order_by("code")
        account_type = self.request.query_params.get("account_type")
        if account_type:
            qs = qs.filter(account_type=account_type)
        return qs


class CostCenterViewSet(TenantModelViewSet):
    serializer_class = CostCenterSerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES


class ExpenseCategoryViewSet(TenantModelViewSet):
    serializer_class = ExpenseCategorySerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES


class JournalEntryViewSet(TenantModelViewSet):
    serializer_class = JournalEntrySerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES
    action_role_map = {
        "list": FINANCIAL_ROLES | ADMIN_ROLES,
        "retrieve": FINANCIAL_ROLES | ADMIN_ROLES,
        "create": FINANCIAL_ROLES,
        "post": FINANCIAL_ROLES,
        "reverse": FINANCIAL_ROLES,
    }

    def get_queryset(self):
        qs = JournalEntry.objects.filter(school=self.get_school(), is_archived=False).prefetch_related("lines__account").select_related("fiscal_period", "posted_by")
        status_filter = self.request.query_params.get("status")
        source_module = self.request.query_params.get("source_module")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if source_module:
            qs = qs.filter(source_module=source_module)
        start = self.request.query_params.get("from")
        end = self.request.query_params.get("to")
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs.order_by("-date", "-created_at")

    def create(self, request, *args, **kwargs):
        serializer = JournalEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        school = self.get_school()
        period = get_object_or_404(FiscalPeriod, pk=data["fiscal_period_id"], school=school, is_archived=False)
        if period.is_closed or period.fiscal_year.is_closed or not (period.start_date <= data["date"] <= period.end_date):
            raise ValidationError("الفترة المالية مغلقة أو تاريخ القيد خارج حدودها.")
        with transaction.atomic():
            entry_number = request.data.get("entry_number") or f"MAN-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
            entry = JournalEntry.objects.create(
                school=school, fiscal_period=period, entry_number=entry_number,
                date=data["date"], description=data["description"],
                status=JournalEntry.Status.DRAFT, source_module="manual_api",
                source_reference="",
            )
            for item in data["lines"]:
                account = get_object_or_404(Account, pk=item["account_id"], school=school, is_leaf=True)
                cost_center = None
                if item.get("cost_center_id"):
                    cost_center = get_object_or_404(CostCenter, pk=item["cost_center_id"], school=school)
                JournalEntryLine.objects.create(
                    school=school, journal_entry=entry, account=account,
                    cost_center=cost_center,
                    debit=Decimal(str(item.get("debit", "0"))),
                    credit=Decimal(str(item.get("credit", "0"))),
                    description=item.get("description", ""),
                )
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        entry = self.get_object()
        if entry.status != JournalEntry.Status.DRAFT:
            raise ValidationError("لا يمكن تعديل قيد مرحّل؛ استخدم قيداً عكسياً.")
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.status == JournalEntry.Status.POSTED:
            raise ValidationError("لا يمكن أرشفة قيد مرحّل؛ أنشئ قيداً عكسياً أولاً.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="post")
    def post(self, request, pk=None):
        with transaction.atomic():
            entry = get_object_or_404(
                JournalEntry.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            if entry.status != JournalEntry.Status.DRAFT:
                raise ValidationError("القيد ليس في حالة مسودة.")
            entry.post(user=request.user)
        return Response(self.get_serializer(entry).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 3:
            raise ValidationError({"reason": "سبب عكس القيد مطلوب."})
        with transaction.atomic():
            entry = get_object_or_404(
                JournalEntry.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            try:
                reversed_entry = reverse_journal_entry(
                    entry, reason=reason, reversed_by=request.user,
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        return Response({
            "reversed_entry_id": str(reversed_entry.pk),
            "entry": self.get_serializer(entry).data,
        }, status=status.HTTP_201_CREATED)


class VoucherBaseViewSet(TenantModelViewSet):
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES

    def perform_create(self, serializer):
        raise MethodNotAllowed(
            "POST",
            detail="استخدم إنشاء السند المخصص لضمان إنشاء قيد مزدوج مرتبط.",
        )

    def perform_update(self, serializer):
        raise MethodNotAllowed(
            "PATCH",
            detail="لا يمكن تعديل سند بعد إنشائه لأن له قيداً مزدوجاً مرتبطاً؛ ألغِ المسودة وأعد إنشاءها.",
        )

    def perform_destroy(self, instance):
        if instance.status != "draft":
            raise ValidationError("لا يمكن أرشفة سند مالي مرحّل؛ استخدم إجراء العكس المعتمد.")
        entry = instance.journal_entry
        super().perform_destroy(instance)
        if entry and entry.status == JournalEntry.Status.DRAFT:
            entry.delete()


class PaymentVoucherViewSet(VoucherBaseViewSet):
    serializer_class = PaymentVoucherSerializer

    def get_queryset(self):
        return PaymentVoucher.objects.filter(school=self.get_school(), is_archived=False).select_related("debit_account", "credit_account", "journal_entry").order_by("-date")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        school = self.get_school()
        debit = get_object_or_404(Account, pk=d["debit_account"].pk, school=school, is_leaf=True)
        credit = get_object_or_404(Account, pk=d["credit_account"].pk, school=school, is_leaf=True)
        amount = d["amount"]
        if amount <= 0:
            raise ValidationError({"amount": "المبلغ يجب أن يكون أكبر من صفر."})
        if debit.account_type != Account.AccountType.EXPENSE:
            raise ValidationError({"debit_account": "حساب المصروف يجب أن يكون من نوع المصروفات."})
        if credit.account_type != Account.AccountType.ASSET:
            raise ValidationError({"credit_account": "حساب الدفع يجب أن يكون من نوع الأصول النقدية/البنكية."})
        period = FiscalPeriod.objects.filter(school=school, is_closed=False, start_date__lte=d["date"], end_date__gte=d["date"], is_archived=False).first()
        if not period or period.fiscal_year.is_closed:
            raise ValidationError("لا توجد فترة مالية مفتوحة لتاريخ السند.")
        with transaction.atomic():
            entry = JournalEntry.objects.create(
                school=school, fiscal_period=period,
                entry_number=f"JV-PAY-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                date=d["date"], description=d["description"],
                status=JournalEntry.Status.DRAFT, source_module="payment_voucher_api",
            )
            JournalEntryLine.objects.create(school=school, journal_entry=entry, account=debit, cost_center=d.get("cost_center"), debit=amount, credit=Decimal("0.00"), description=d["description"])
            JournalEntryLine.objects.create(school=school, journal_entry=entry, account=credit, cost_center=d.get("cost_center"), debit=Decimal("0.00"), credit=amount, description=d["description"])
            voucher = PaymentVoucher.objects.create(
                school=school, voucher_number=d.get("voucher_number") or f"PV-{entry.entry_number[-12:]}",
                date=d["date"], paid_to=d["paid_to"], amount=amount, payment_method=d["payment_method"],
                credit_account=credit, debit_account=debit, cost_center=d.get("cost_center"),
                description=d["description"], reference_number=d.get("reference_number", ""),
                status=PaymentVoucher.Status.DRAFT, journal_entry=entry,
            )
        return Response(self.get_serializer(voucher).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="post")
    def post(self, request, pk=None):
        with transaction.atomic():
            voucher = get_object_or_404(
                PaymentVoucher.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            if voucher.status != PaymentVoucher.Status.DRAFT:
                raise ValidationError("السند ليس مسودة.")
            entry = get_object_or_404(
                JournalEntry.objects.select_for_update(),
                pk=voucher.journal_entry_id, school=self.get_school(),
            )
            entry.post(user=request.user)
            voucher.status = PaymentVoucher.Status.POSTED
            voucher.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(voucher).data)


class ReceiptVoucherViewSet(VoucherBaseViewSet):
    serializer_class = ReceiptVoucherSerializer

    def get_queryset(self):
        return ReceiptVoucher.objects.filter(school=self.get_school(), is_archived=False).select_related("debit_account", "credit_account", "journal_entry").order_by("-date")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        school = self.get_school()
        debit = get_object_or_404(Account, pk=d["debit_account"].pk, school=school, is_leaf=True, account_type=Account.AccountType.ASSET)
        credit = get_object_or_404(
            Account, pk=d["credit_account"].pk, school=school,
            is_leaf=True, account_type=Account.AccountType.REVENUE,
        )
        if d["amount"] <= 0:
            raise ValidationError({"amount": "المبلغ يجب أن يكون أكبر من صفر."})
        period = FiscalPeriod.objects.filter(school=school, is_closed=False, start_date__lte=d["date"], end_date__gte=d["date"], is_archived=False).first()
        if not period or period.fiscal_year.is_closed:
            raise ValidationError("لا توجد فترة مالية مفتوحة لتاريخ السند.")
        with transaction.atomic():
            entry = JournalEntry.objects.create(
                school=school, fiscal_period=period,
                entry_number=f"JV-REC-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                date=d["date"], description=d["description"],
                status=JournalEntry.Status.DRAFT, source_module="receipt_voucher_api",
            )
            JournalEntryLine.objects.create(school=school, journal_entry=entry, account=debit, cost_center=d.get("cost_center"), debit=d["amount"], credit=Decimal("0.00"), description=d["description"])
            JournalEntryLine.objects.create(school=school, journal_entry=entry, account=credit, cost_center=d.get("cost_center"), debit=Decimal("0.00"), credit=d["amount"], description=d["description"])
            voucher = ReceiptVoucher.objects.create(
                school=school, voucher_number=d.get("voucher_number") or f"RV-{entry.entry_number[-12:]}",
                date=d["date"], received_from=d["received_from"], amount=d["amount"], payment_method=d["payment_method"],
                debit_account=debit, credit_account=credit, cost_center=d.get("cost_center"),
                description=d["description"], reference_number=d.get("reference_number", ""),
                status=ReceiptVoucher.Status.DRAFT, journal_entry=entry,
            )
        return Response(self.get_serializer(voucher).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="post")
    def post(self, request, pk=None):
        with transaction.atomic():
            voucher = get_object_or_404(
                ReceiptVoucher.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            if voucher.status != ReceiptVoucher.Status.DRAFT:
                raise ValidationError("السند ليس مسودة.")
            entry = get_object_or_404(
                JournalEntry.objects.select_for_update(),
                pk=voucher.journal_entry_id, school=self.get_school(),
            )
            entry.post(user=request.user)
            voucher.status = ReceiptVoucher.Status.POSTED
            voucher.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(voucher).data)


# ---------------------------------------------------------------------------
# Procurement, stock and fixed assets
# ---------------------------------------------------------------------------
class SupplierViewSet(TenantModelViewSet):
    serializer_class = SupplierSerializer
    read_roles = INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = INVENTORY_ROLES


class WarehouseViewSet(TenantModelViewSet):
    serializer_class = WarehouseSerializer
    read_roles = INVENTORY_ROLES | ADMIN_ROLES
    write_roles = INVENTORY_ROLES


class InventoryItemViewSet(TenantModelViewSet):
    serializer_class = InventoryItemSerializer
    read_roles = INVENTORY_ROLES | ADMIN_ROLES | {"teacher"}
    write_roles = INVENTORY_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("warehouse")
        warehouse = self.request.query_params.get("warehouse_id")
        low_stock = self.request.query_params.get("low_stock")
        if warehouse:
            qs = qs.filter(warehouse_id=warehouse)
        if low_stock in ("1", "true"):
            qs = qs.filter(current_stock__lte=F("reorder_level"))
        return qs.order_by("name")


class StockMovementViewSet(TenantModelViewSet):
    serializer_class = StockMovementSerializer
    read_roles = INVENTORY_ROLES | ADMIN_ROLES
    write_roles = INVENTORY_ROLES

    def perform_destroy(self, instance):
        # The model's delete() reverses the physical stock effect atomically.
        instance.delete()

    def get_queryset(self):
        qs = super().get_queryset().select_related("item")
        item_id = self.request.query_params.get("item_id")
        movement_type = self.request.query_params.get("movement_type")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        return qs.order_by("-date", "-created_at")


class PurchaseOrderViewSet(TenantModelViewSet):
    serializer_class = PurchaseOrderSerializer
    read_roles = INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = INVENTORY_ROLES
    action_role_map = {
        "list": INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES,
        "retrieve": INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES,
        "approve": FINANCIAL_ROLES | ADMIN_ROLES,
        "receive": INVENTORY_ROLES | ADMIN_ROLES,
    }

    def get_queryset(self):
        return PurchaseOrder.objects.filter(
            school=self.get_school(), is_archived=False,
        ).prefetch_related("items__item").order_by("-order_date")

    def perform_create(self, serializer):
        school = self.get_school()
        supplier = get_object_or_404(
            Supplier, pk=serializer.validated_data["supplier"].pk,
            school=school, is_archived=False, is_active=True,
        )
        warehouse = get_object_or_404(
            Warehouse, pk=serializer.validated_data["warehouse"].pk,
            school=school, is_archived=False,
        )
        serializer.save(school=school, supplier=supplier, warehouse=warehouse)

    def perform_update(self, serializer):
        if serializer.instance.status != PurchaseOrder.Status.DRAFT:
            raise ValidationError("لا يمكن تعديل أمر شراء بعد اعتماده.")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        with transaction.atomic():
            order = get_object_or_404(
                PurchaseOrder.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            if order.status != PurchaseOrder.Status.DRAFT:
                raise ValidationError("أمر الشراء ليس في حالة مسودة.")
            if not order.items.filter(is_archived=False).exists():
                raise ValidationError("أضف بنداً واحداً على الأقل قبل اعتماد أمر الشراء.")
            order.total_amount = sum(
                (item.total_price for item in order.items.filter(is_archived=False)),
                Decimal("0.00"),
            )
            order.status = PurchaseOrder.Status.APPROVED
            order.approved_by = request.user
            order.save(update_fields=[
                "total_amount", "status", "approved_by", "updated_at",
            ])
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, pk=None):
        order = self.get_object()
        movements = order.receive_into_warehouse(user=request.user)
        return Response({"status": order.status, "created_movements": [str(x.pk) for x in movements]})


class PurchaseOrderItemViewSet(TenantModelViewSet):
    serializer_class = PurchaseOrderItemSerializer
    read_roles = INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = INVENTORY_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("purchase_order", "item")
        order_id = self.request.query_params.get("purchase_order_id")
        return qs.filter(purchase_order_id=order_id) if order_id else qs

    def _recalculate_order_total(self, order):
        total = order.items.filter(is_archived=False).aggregate(
            total=Sum("total_price"),
        )["total"] or Decimal("0.00")
        order.total_amount = total
        order.save(update_fields=["total_amount", "updated_at"])

    def perform_create(self, serializer):
        school = self.get_school()
        with transaction.atomic():
            order = get_object_or_404(
                PurchaseOrder.objects.select_for_update(),
                pk=serializer.validated_data["purchase_order"].pk,
                school=school, status=PurchaseOrder.Status.DRAFT,
                is_archived=False,
            )
            item = get_object_or_404(
                InventoryItem, pk=serializer.validated_data["item"].pk,
                school=school, is_archived=False,
            )
            serializer.save(school=school, purchase_order=order, item=item)
            self._recalculate_order_total(order)

    def perform_update(self, serializer):
        school = self.get_school()
        with transaction.atomic():
            order = get_object_or_404(
                PurchaseOrder.objects.select_for_update(),
                pk=serializer.instance.purchase_order_id,
                school=school, status=PurchaseOrder.Status.DRAFT,
                is_archived=False,
            )
            if (
                "purchase_order" in serializer.validated_data
                and serializer.validated_data["purchase_order"].pk != order.pk
            ):
                raise ValidationError("لا يمكن نقل بند بين أوامر شراء مختلفة.")
            if "item" in serializer.validated_data:
                serializer.validated_data["item"] = get_object_or_404(
                    InventoryItem, pk=serializer.validated_data["item"].pk,
                    school=school, is_archived=False,
                )
            serializer.save(purchase_order=order)
            self._recalculate_order_total(order)

    def perform_destroy(self, instance):
        school = self.get_school()
        with transaction.atomic():
            order = get_object_or_404(
                PurchaseOrder.objects.select_for_update(),
                pk=instance.purchase_order_id, school=school,
                status=PurchaseOrder.Status.DRAFT, is_archived=False,
            )
            instance.archive(actor=self.request.user, reason="أرشفة بند أمر الشراء")
            self._recalculate_order_total(order)


class VendorInvoiceViewSet(TenantModelViewSet):
    serializer_class = VendorInvoiceSerializer
    read_roles = INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES
    action_role_map = {
        "list": INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES,
        "retrieve": INVENTORY_ROLES | FINANCIAL_ROLES | ADMIN_ROLES,
        "approve": FINANCIAL_ROLES,
        "post": FINANCIAL_ROLES,
        "record_payment": FINANCIAL_ROLES,
    }

    def get_queryset(self):
        return VendorInvoice.objects.filter(school=self.get_school(), is_archived=False).select_related("supplier", "purchase_order", "journal_entry").order_by("-invoice_date")

    def perform_create(self, serializer):
        serializer.save(school=self.get_school(), status=VendorInvoice.Status.DRAFT)

    def perform_update(self, serializer):
        if serializer.instance.status != VendorInvoice.Status.DRAFT or serializer.instance.journal_entry_id:
            raise ValidationError("لا يمكن تعديل فاتورة مورد بعد اعتمادها أو ترحيلها.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != VendorInvoice.Status.DRAFT or instance.journal_entry_id:
            raise ValidationError("لا يمكن أرشفة فاتورة مورد معتمدة أو مرحّلة.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        with transaction.atomic():
            invoice = get_object_or_404(
                VendorInvoice.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            if invoice.status != VendorInvoice.Status.DRAFT:
                raise ValidationError("لا يمكن اعتماد الفاتورة إلا من حالة مسودة.")
            invoice.status = VendorInvoice.Status.APPROVED
            invoice.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post(self, request, pk=None):
        from apps.accounting.services.auto_posting import (
            _get_account_or_seed, _get_active_fiscal_period,
        )
        school = self.get_school()
        with transaction.atomic():
            invoice = get_object_or_404(
                VendorInvoice.objects.select_for_update(),
                pk=pk, school=school, is_archived=False,
            )
            if invoice.status != VendorInvoice.Status.APPROVED:
                raise ValidationError("يجب اعتماد فاتورة المورد قبل ترحيلها.")
            if invoice.journal_entry_id:
                raise ValidationError("تم ترحيل الفاتورة محاسبياً مسبقاً.")
            period = _get_active_fiscal_period(school, invoice.invoice_date)
            ap = _get_account_or_seed(school, "2101", "ذمم الموردين")
            expense = _get_account_or_seed(school, "5101", "مشتريات ومستلزمات مدرسية")
            entry = JournalEntry.objects.create(
                school=school, fiscal_period=period,
                entry_number=f"JV-VENDOR-{invoice.invoice_number}",
                date=invoice.invoice_date, description=f"فاتورة مورد #{invoice.invoice_number}",
                status=JournalEntry.Status.DRAFT, source_module="vendor_invoice",
                source_reference=str(invoice.pk),
            )
            JournalEntryLine.objects.create(school=school, journal_entry=entry, account=expense, debit=invoice.total_amount, credit=Decimal("0.00"), description=invoice.notes or invoice.invoice_number)
            JournalEntryLine.objects.create(school=school, journal_entry=entry, account=ap, debit=Decimal("0.00"), credit=invoice.total_amount, description=f"استحقاق المورد {invoice.supplier.name}")
            entry.post(user=request.user)
            invoice.journal_entry = entry
            invoice.save(update_fields=["journal_entry", "updated_at"])
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        try:
            amount = Decimal(str(request.data.get("amount")))
        except Exception:
            raise ValidationError({"amount": "المبلغ غير صحيح."})
        payment_account = get_object_or_404(
            Account, pk=request.data.get("payment_account_id"),
            school=self.get_school(), is_leaf=True,
            account_type=Account.AccountType.ASSET,
        )
        from apps.accounting.services.auto_posting import (
            _get_account_or_seed, _get_active_fiscal_period,
        )
        with transaction.atomic():
            invoice = get_object_or_404(
                VendorInvoice.objects.select_for_update(),
                pk=pk, school=self.get_school(), is_archived=False,
            )
            if not invoice.journal_entry_id:
                raise ValidationError("يجب ترحيل فاتورة المورد محاسبياً قبل تسجيل السداد.")
            if invoice.status not in [VendorInvoice.Status.APPROVED, VendorInvoice.Status.PARTIAL]:
                raise ValidationError("فاتورة المورد ليست في حالة تسمح بالسداد.")
            if amount <= 0 or amount > invoice.remaining_amount:
                raise ValidationError({
                    "amount": f"المبلغ يجب أن يكون أكبر من صفر ولا يتجاوز المتبقي {invoice.remaining_amount}.",
                })
            period = _get_active_fiscal_period(self.get_school(), timezone.localdate())
            ap = _get_account_or_seed(self.get_school(), "2101", "ذمم الموردين")
            entry = JournalEntry.objects.create(
                school=self.get_school(), fiscal_period=period,
                entry_number=f"JV-VENDOR-PAY-{invoice.pk.hex[:8]}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                date=timezone.localdate(), description=f"سداد فاتورة المورد #{invoice.invoice_number}",
                status=JournalEntry.Status.DRAFT, source_module="vendor_invoice_payment", source_reference=str(invoice.pk),
            )
            JournalEntryLine.objects.create(school=self.get_school(), journal_entry=entry, account=ap, debit=amount, credit=Decimal("0.00"), description="تسوية ذمم المورد")
            JournalEntryLine.objects.create(school=self.get_school(), journal_entry=entry, account=payment_account, debit=Decimal("0.00"), credit=amount, description="السداد من الصندوق/البنك")
            entry.post(user=request.user)
            invoice.paid_amount += amount
            invoice.status = VendorInvoice.Status.PAID if invoice.paid_amount == invoice.total_amount else VendorInvoice.Status.PARTIAL
            invoice.save(update_fields=["paid_amount", "status", "updated_at"])
        return Response(self.get_serializer(invoice).data)


class AssetCategoryViewSet(TenantModelViewSet):
    serializer_class = AssetCategorySerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES


class FixedAssetViewSet(TenantModelViewSet):
    serializer_class = FixedAssetSerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES

    def get_queryset(self):
        return super().get_queryset().select_related("category", "custodian").order_by("name")


class AssetDepreciationViewSet(TenantModelViewSet):
    serializer_class = AssetDepreciationSerializer
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES

    def get_queryset(self):
        return super().get_queryset().select_related("asset", "fiscal_year").order_by("-date")

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT", detail="سجل الإهلاك قيد مالي تاريخي غير قابل للتعديل.")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH", detail="سجل الإهلاك قيد مالي تاريخي غير قابل للتعديل.")

    def perform_destroy(self, instance):
        raise ValidationError("لا يمكن أرشفة قيد إهلاك مسجل؛ يجب إنشاء قيد تسوية محاسبي.")

    def perform_create(self, serializer):
        school = self.get_school()
        data = serializer.validated_data
        with transaction.atomic():
            asset = get_object_or_404(FixedAsset.objects.select_for_update(), pk=data["asset"].pk, school=school, is_archived=False)
            entry = AssetDepreciationEntry(
                school=school, asset=asset, fiscal_year=data["fiscal_year"],
                depreciation_amount=data["depreciation_amount"], date=data["date"],
            )
            entry.full_clean()
            entry.save()
            asset.accumulated_depreciation += entry.depreciation_amount
            asset.save(update_fields=["accumulated_depreciation", "updated_at"])
            serializer.instance = entry


# ---------------------------------------------------------------------------
# Notification devices/preferences and secure conversation messaging
# ---------------------------------------------------------------------------
class PushDeviceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PushDeviceSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return PushDevice.objects.filter(user=self.request.user).order_by("-last_seen_at")

    def list(self, request):
        devices = PushDevice.objects.filter(user=request.user).order_by("-last_seen_at")
        return Response(PushDeviceSerializer(devices, many=True).data)

    def create(self, request):
        serializer = PushDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                device, created = PushDevice.objects.update_or_create(
                    user=request.user, device_id=data["device_id"],
                    defaults={
                        "platform": data["platform"],
                        "push_token": data["push_token"],
                        "app_version": data.get("app_version", ""),
                        "device_name": data.get("device_name", ""),
                        "is_active": True,
                        "last_seen_at": timezone.now(),
                    },
                )
        except IntegrityError as exc:
            raise ValidationError({
                "push_token": "رمز الإشعارات مسجل مسبقاً على جهاز أو حساب آخر.",
            }) from exc
        return Response(
            PushDeviceSerializer(device).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        device = get_object_or_404(PushDevice, pk=pk, user=request.user)
        device.is_active = False
        device.save(update_fields=["is_active", "updated_at"])
        return Response({"id": str(device.pk), "is_active": False})

    @action(detail=True, methods=["post"], url_path="heartbeat")
    def heartbeat(self, request, pk=None):
        device = get_object_or_404(PushDevice, pk=pk, user=request.user)
        device.last_seen_at = timezone.now()
        device.is_active = True
        device.save(update_fields=["last_seen_at", "is_active", "updated_at"])
        return Response({"id": str(device.pk), "last_seen_at": device.last_seen_at})


class NotificationPreferenceViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        school = school_for(request)
        qs = NotificationPreference.objects.filter(user=request.user).filter(Q(school=school) | Q(school__isnull=True)).order_by("category", "channel")
        return Response(NotificationPreferenceSerializer(qs, many=True).data)

    def create(self, request):
        school = school_for(request)
        serializer = NotificationPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pref, created = NotificationPreference.objects.update_or_create(
            user=request.user, school=school,
            category=data["category"], channel=data["channel"],
            defaults={"is_enabled": data["is_enabled"]},
        )
        return Response(NotificationPreferenceSerializer(pref).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        pref = get_object_or_404(NotificationPreference, pk=pk, user=request.user)
        if pref.school_id and pref.school_id != school_for(request).pk:
            raise Http404
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, school=pref.school)
        return Response(serializer.data)


class SchoolConversationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_school(self):
        return school_for(self.request)

    def get_participant(self, conversation):
        return get_object_or_404(
            ConversationParticipant,
            school=self.get_school(), conversation=conversation,
            user=self.request.user, is_active=True, is_archived=False,
        )

    def get_queryset(self):
        school = self.get_school()
        return SchoolConversation.objects.filter(
            school=school, is_archived=False,
            participants__user=self.request.user,
            participants__is_active=True,
            participants__is_archived=False,
        ).distinct().prefetch_related("participants__user", "messages")

    def list(self, request):
        qs = self.get_queryset()
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(SchoolConversationSerializer(qs[:100], many=True, context={"request": request}).data)

    def retrieve(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(SchoolConversationSerializer(conv, context={"request": request}).data)

    def create(self, request):
        school = self.get_school()
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        participant_ids = list(dict.fromkeys([request.user.pk] + data["participant_ids"]))
        members = {
            str(x.user_id): x for x in SchoolMembership.objects.filter(
                school=school, user_id__in=participant_ids,
                status=SchoolMembership.Status.ACTIVE,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        }
        missing = set(map(str, participant_ids)) - set(members)
        if missing:
            raise ValidationError({"participant_ids": "كل المشاركين يجب أن تكون لديهم عضوية نشطة وسارية في المدرسة."})
        student = None
        if data.get("student_id"):
            student = get_object_or_404(Student, pk=data["student_id"], school=school, is_archived=False)
            # Parent may start a conversation only about a linked child.
            guardian = user_guardian_profiles(request.user, school).first()
            if guardian and not is_admin(request.user, school) and not guardian.children.filter(pk=student.pk).exists():
                raise PermissionDenied("الطالب المرتبط بالمحادثة ليس من الأبناء المسجلين في حسابك.")
        if not is_admin(request.user, school):
            if user_guardian_profiles(request.user, school).exists() and not student:
                raise ValidationError("حدد الطالب المرتبط بالمحادثة للتحقق من صلة ولي الأمر.")
        with transaction.atomic():
            conv = SchoolConversation.objects.create(
                school=school, subject=data["subject"],
                conversation_type=data["conversation_type"],
                student=student, created_by=request.user,
            )
            for user_id in participant_ids:
                user = members[str(user_id)].user
                role = self._participant_role(user, school)
                ConversationParticipant.objects.create(
                    school=school, conversation=conv, user=user,
                    role=role, added_by=request.user,
                )
        return Response(SchoolConversationSerializer(conv, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def _participant_role(self, user, school):
        if has_school_roles(user, school, ADMIN_ROLES):
            return ConversationParticipant.Role.ADMIN
        if user_teacher_profiles(user, school).exists():
            return ConversationParticipant.Role.TEACHER
        if user_guardian_profiles(user, school).exists():
            return ConversationParticipant.Role.GUARDIAN
        if user_student_profiles(user, school).exists():
            return ConversationParticipant.Role.STUDENT
        return ConversationParticipant.Role.STAFF

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        participant = self.get_participant(conv)
        if request.method == "GET":
            qs = conv.messages.filter(is_archived=False, is_deleted=False).select_related("sender").order_by("created_at")
            before = request.query_params.get("before")
            if before:
                qs = qs.filter(created_at__lt=before)
            items = list(qs[:100])
            return Response({
                "results": ConversationMessageSerializer(items, many=True).data,
                "has_more": qs.count() > len(items),
            })
        serializer = MessageCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if conv.status != SchoolConversation.Status.OPEN:
            raise ValidationError("المحادثة مغلقة ولا تقبل رسائل جديدة.")
        attachment = request.FILES.get("attachment")
        if attachment:
            extension = os.path.splitext(attachment.name)[1].lower()
            if extension not in {
                ".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx",
                ".xls", ".xlsx", ".txt",
            }:
                raise ValidationError({"attachment": "نوع الملف غير مدعوم للمحادثات."})
            if attachment.size > 15 * 1024 * 1024:
                raise ValidationError({"attachment": "الحد الأقصى لحجم المرفق 15 ميجابايت."})
        reply = None
        if serializer.validated_data.get("reply_to_id"):
            reply = get_object_or_404(conv.messages, pk=serializer.validated_data["reply_to_id"], is_archived=False)
        with transaction.atomic():
            message = ConversationMessage.objects.create(
                school=self.get_school(), conversation=conv,
                sender=request.user,
                body=serializer.validated_data.get("body", ""),
                attachment=attachment,
                attachment_name=os.path.basename(attachment.name) if attachment else "",
                attachment_size=attachment.size if attachment else 0,
                message_type=ConversationMessage.MessageType.FILE if attachment else ConversationMessage.MessageType.TEXT,
                reply_to=reply,
            )
            conv.last_message_at = message.created_at
            conv.save(update_fields=["last_message_at", "updated_at"])
            Notification.objects.bulk_create([
                Notification(
                    school=self.get_school(), recipient=p.user,
                    channel=Notification.Channel.IN_APP, category="conversation",
                    title=f"رسالة جديدة: {conv.subject}",
                    body=message.body[:400] or "تم إرسال مرفق جديد.",
                    action_url=f"/messages/{conv.pk}",
                    payload={"conversation_id": str(conv.pk), "message_id": str(message.pk)},
                    idempotency_key=f"conversation:{message.pk}:{p.user_id}",
                )
                for p in conv.participants.filter(is_active=True, is_archived=False).exclude(user=request.user)
            ], ignore_conflicts=True)
        return Response(ConversationMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        participant = self.get_participant(conv)
        participant.last_read_at = timezone.now()
        participant.save(update_fields=["last_read_at", "updated_at"])
        return Response({"conversation_id": str(conv.pk), "last_read_at": participant.last_read_at})

    @action(detail=True, methods=["post"], url_path="mute")
    def mute(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        participant = self.get_participant(conv)
        participant.is_muted = bool(request.data.get("muted", True))
        participant.save(update_fields=["is_muted", "updated_at"])
        return Response({"conversation_id": str(conv.pk), "is_muted": participant.is_muted})

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        self.get_participant(conv)
        require_school_role_or_permission(request, self.get_school(), ADMIN_ROLES)
        conv.status = SchoolConversation.Status.CLOSED
        conv.save(update_fields=["status", "updated_at"])
        return Response({"id": str(conv.pk), "status": conv.status})


class ConversationMessageDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_message(self, request, conversation_id, message_id):
        school = school_for(request)
        conversation = get_object_or_404(
            SchoolConversation, pk=conversation_id, school=school,
            is_archived=False,
        )
        participant = get_object_or_404(
            ConversationParticipant, school=school,
            conversation=conversation, user=request.user,
            is_active=True, is_archived=False,
        )
        message = get_object_or_404(
            ConversationMessage, pk=message_id, school=school,
            conversation=conversation, is_archived=False,
        )
        return school, conversation, participant, message

    def patch(self, request, conversation_id, message_id):
        school, conversation, participant, message = self._get_message(
            request, conversation_id, message_id,
        )
        if message.sender_id != request.user.pk or message.is_deleted:
            raise PermissionDenied("يمكنك تعديل رسائلك غير المحذوفة فقط.")
        if conversation.status != SchoolConversation.Status.OPEN:
            raise ValidationError("المحادثة مغلقة.")
        body = request.data.get("body")
        if not isinstance(body, str) or not body.strip():
            raise ValidationError({"body": "نص الرسالة مطلوب."})
        if len(body) > 10000:
            raise ValidationError({"body": "الحد الأقصى لطول الرسالة 10000 حرف."})
        message.body = body.strip()
        message.edited_at = timezone.now()
        message.save(update_fields=["body", "edited_at", "updated_at"])
        return Response(ConversationMessageSerializer(message).data)

    def delete(self, request, conversation_id, message_id):
        school, conversation, participant, message = self._get_message(
            request, conversation_id, message_id,
        )
        if (
            message.sender_id != request.user.pk
            and not is_admin(request.user, school)
        ):
            raise PermissionDenied("لا يمكنك حذف رسالة أرسلها مستخدم آخر.")
        if message.is_deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        message.is_deleted = True
        message.edited_at = timezone.now()
        message.save(update_fields=["is_deleted", "edited_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationAttachmentDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, message_id):
        school = school_for(request)
        message = get_object_or_404(
            ConversationMessage.objects.select_related("conversation"),
            pk=message_id, school=school, is_archived=False, is_deleted=False,
        )
        allowed = ConversationParticipant.objects.filter(
            school=school, conversation=message.conversation, user=request.user,
            is_active=True, is_archived=False,
        ).exists()
        if not allowed or not message.attachment:
            raise Http404
        filename = message.attachment_name or os.path.basename(message.attachment.name)
        return FileResponse(message.attachment.open("rb"), as_attachment=True, filename=filename)


class HomeworkAttachmentDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, submission_id):
        school = school_for(request)
        submission = get_object_or_404(
            HomeworkSubmission.objects.select_related("homework", "student"),
            pk=submission_id, school=school, is_archived=False,
        )
        allowed = is_admin(request.user, school)
        if has_school_roles(request.user, school, {"student"}):
            student = user_student_profiles(request.user, school).first()
            allowed = bool(student and submission.student_id == student.pk)
        elif has_school_roles(request.user, school, {"guardian"}):
            guardian = user_guardian_profiles(request.user, school).first()
            allowed = bool(guardian and guardian.children.filter(pk=submission.student_id).exists())
        elif has_school_roles(request.user, school, {"teacher"}):
            teacher = user_teacher_profiles(request.user, school).first()
            allowed = bool(teacher and submission.homework.teacher_id == teacher.pk)
        if not allowed or not submission.attachment:
            raise Http404
        filename = os.path.basename(submission.attachment.name)
        return FileResponse(submission.attachment.open("rb"), as_attachment=True, filename=filename)
