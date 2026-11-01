"""Versioned REST API surface for the multi-role School mobile application."""
from __future__ import annotations

import hashlib
import os
from uuid import UUID
from decimal import Decimal
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import F, Max, Q, Sum
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
    FINANCIAL_ROLES, STUDENT_AFFAIRS_ROLES,
    has_school_roles, require_school_role_or_permission, resolve_active_school,
)
from apps.accounts.models import (
    MembershipRole, SchoolInvitation, SchoolMembership, SchoolRole, User,
)
from apps.accounts.services import (
    accept_school_invitation, active_membership, issue_school_invitation,
)
from apps.accounts.session_services import send_phone_message
from apps.academics.models import AcademicTerm, AcademicYear, Section
from apps.accounting.models import (
    Account, CostCenter, FiscalPeriod, JournalEntry, JournalEntryLine,
    PaymentVoucher, ReceiptVoucher,
)
from apps.accounting.services.auto_posting import reverse_journal_entry
from apps.assets.models import AssetDepreciationEntry, FixedAsset
from apps.assessments.models import (
    ExamCommittee, GradeBook, OnlineExam, QuestionBank,
    StudentOnlineExamSubmission,
)
from apps.assignments.models import (
    Homework, HomeworkSubmission, HomeworkSubmissionAttempt,
)
from apps.auditlog.services import record_event
from apps.inventory.models import (
    InventoryItem, PurchaseOrder, Supplier, VendorInvoice, Warehouse,
)
from apps.notifications.models import (
    ConversationMessage, ConversationParticipant, Notification,
    NotificationPreference, PushDevice, SchoolConversation,
)
from apps.staff.models import (
    StaffMember, Teacher, TeacherAssignment,
)
from apps.students.models import (
    Guardian, Student, StudentGuardianRelation,
)
from apps.students.services import ensure_guardian_membership
from apps.timetable.models import (
    ClassSchedule, SchoolBellSchedule, TimetablePlan,
)
from apps.tenants.models import Branch

from apps.api.v1.serializers import (
    AcademicTermSerializer, AcademicYearSerializer, AccountSerializer,
    AssetCategorySerializer, AssetDepreciationSerializer, AssessmentTypeSerializer,
    BranchSerializer,
    ClassroomSerializer, ClassScheduleSerializer, ConversationCreateSerializer,
    ConversationMessageSerializer,
    CostCenterSerializer, DailyLessonLogSerializer, DepartmentSerializer,
    EducationalStageSerializer, ExamCommitteeProctorSerializer, ExamCommitteeSerializer,
    ExamPaperQuestionSerializer, ExamSeatingSerializer, ExamSubmissionReviewSerializer,
    ExpenseCategorySerializer, FiscalPeriodSerializer, FiscalYearSerializer,
    FixedAssetSerializer, GradeBookSerializer, GradeLevelSerializer,
    GuardianSerializer, HomeworkSerializer, HomeworkSubmissionSerializer,
    InvitationSerializer, InventoryItemSerializer, JournalEntryCreateSerializer,
    JournalEntrySerializer, JournalEntryUpdateSerializer, LeaveTypeSerializer,
    MembershipRoleSerializer, MembershipSerializer, MessageCreateSerializer,
    NotificationPreferenceSerializer, OnlineExamSerializer, PaymentVoucherSerializer,
    PeriodDefinitionSerializer, PushDeviceSerializer, PurchaseOrderItemSerializer,
    PurchaseOrderSerializer, QuestionBankTeacherSerializer, ReceiptVoucherSerializer,
    SchoolBellScheduleSerializer, SchoolConversationSerializer, SchoolRoleSerializer,
    TimetablePlanSerializer, TimetablePlanCopyInputSerializer,
    SchoolWorkingDaySerializer, SchedulePeriodTemplateSerializer, SectionSerializer,
    StockMovementSerializer, StudentGuardianRelationSerializer, SubjectSerializer,
    SupplierSerializer, TeacherAssignmentSerializer, TeacherSerializer,
    VendorInvoiceSerializer, WarehouseSerializer, WorkShiftSerializer,
)

ADMIN_ROLES = {
    "admin", "school-admin", "school_admin",
    "school-director", "school_director",
    "principal", "school-principal",
    "academic-coordinator", "academic_coordinator",
    "student-affairs", "student_affairs",
}
FINANCE_ADMIN_ROLES = FINANCIAL_ROLES | ADMIN_ROLES
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


class AcademicStructureViewSet(TenantModelViewSet):
    """Academic catalogues can be shared by a school or scoped to one branch."""

    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = self.request.query_params.get("branch_id")
        if not branch_id:
            return queryset
        try:
            branch_uuid = UUID(str(branch_id))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError({"branch_id": "أرسل معرف فرع صحيحاً بصيغة UUID."})
        branch = Branch.objects.filter(
            pk=branch_uuid,
            school=self.get_school(),
            is_archived=False,
        ).first()
        if branch is None:
            raise ValidationError({"branch_id": "الفرع غير موجود أو لا يتبع المدرسة النشطة."})
        return queryset.filter(Q(branch_id=branch.pk) | Q(branch__isnull=True))


class BranchViewSet(TenantModelViewSet):
    serializer_class = BranchSerializer
    read_roles = READ_ROLES
    write_roles = ADMIN_ROLES

    def get_queryset(self):
        return super().get_queryset().order_by("-is_main", "name")


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

    def perform_update(self, serializer):
        if serializer.instance.is_system:
            raise ValidationError("لا يمكن تعديل تعريف دور النظام الأساسي من واجهة الأدوار المخصصة.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError("لا يمكن أرشفة دور نظامي أساسي.")
        super().perform_destroy(instance)


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
        if active_membership(user=membership.user, school=school) is None:
            raise ValidationError("لا يمكن إسناد دور لعضوية غير نشطة أو منتهية.")
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
        if active_membership(user=membership.user, school=school) is None:
            raise ValidationError("لا يمكن إسناد دور لعضوية غير نشطة أو منتهية.")
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
        from apps.accounts.models import normalize_phone
        phone = normalize_phone(request.data.get("phone") or "")
        if not email and not phone:
            raise ValidationError({"detail": "أدخل بريداً إلكترونياً أو رقم هاتف لإرسال الدعوة."})
        role_ids = request.data.get("role_ids") or []
        if not isinstance(role_ids, list):
            raise ValidationError({"role_ids": "يجب إرسال الأدوار كمصفوفة من المعرفات."})
        if len(set(map(str, role_ids))) != len(role_ids):
            raise ValidationError({"role_ids": "لا تكرر الدور نفسه في الدعوة."})
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
        delivery_channels = []
        delivery_errors = []
        if email:
            try:
                subject = f"دعوة للانضمام إلى {school.name}"
                body = (
                    f"مرحباً،\n\nتمت دعوتك للانضمام إلى {school.name}.\n"
                    f"رمز قبول الدعوة: {raw_token}\n"
                    f"تنتهي الدعوة في: {invitation.expires_at.isoformat()}\n"
                    "لا تشارك هذا الرمز مع أي شخص."
                )
                sent = send_mail(
                    subject, body, settings.DEFAULT_FROM_EMAIL, [email],
                    fail_silently=False,
                )
                if sent == 1:
                    delivery_channels.append("email")
                else:
                    delivery_errors.append("لم يؤكد مزود البريد تسليم رسالة الدعوة.")
            except Exception:
                delivery_errors.append("فشل تسليم الدعوة عبر البريد الإلكتروني.")
        if phone:
            try:
                send_phone_message(
                    phone=phone,
                    message=f"دعوة الانضمام إلى {school.name}. رمز القبول: {raw_token}",
                    purpose="school_invitation",
                )
                delivery_channels.append("sms")
            except Exception:
                delivery_errors.append("فشل تسليم الدعوة عبر الرسائل النصية.")

        if not delivery_channels:
            invitation.status = SchoolInvitation.Status.REVOKED
            invitation.save(update_fields=["status", "updated_at"])
            return Response(
                {
                    "error": "تعذر تسليم الدعوة عبر أي من قنوات الاتصال؛ ألغيت الدعوة غير المسلمة.",
                    "delivery_errors": delivery_errors,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        data = InvitationSerializer(invitation).data
        data["delivery_channels"] = delivery_channels
        data["delivered"] = bool(delivery_channels)
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

    @transaction.atomic
    def perform_create(self, serializer):
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, STUDENT_AFFAIRS_ROLES,
            "students.add_guardian",
        )
        from apps.accounts.models import normalize_phone

        phone = normalize_phone(self.request.data.get("phone") or "")
        user_id = self.request.data.get("user_id")
        user = None
        if phone:
            user = User.objects.select_for_update().filter(phone=phone).first()
        elif user_id:
            # Compatibility for verified accounts created by earlier integrations.
            user = User.objects.select_for_update().filter(pk=user_id).first()
        if user is None:
            raise ValidationError({"phone": "لم يتم العثور على حساب مستخدم برقم الهاتف المحدد."})
        if Guardian.objects.filter(
            school=school, user=user, is_archived=False,
        ).exists():
            raise ValidationError("يوجد بالفعل ملف ولي أمر لهذا الحساب في المدرسة.")
        ensure_guardian_membership(user=user, school=school, actor=self.request.user)
        serializer.save(school=school, user=user)


class GuardianRelationViewSet(TenantModelViewSet):
    serializer_class = StudentGuardianRelationSerializer
    read_roles = ADMIN_ROLES
    write_roles = STUDENT_AFFAIRS_ROLES

    def get_queryset(self):
        return StudentGuardianRelation.objects.filter(
            school=self.get_school(), is_archived=False,
        ).select_related("student", "guardian__user")

    def _ensure_verified_guardian(self, serializer):
        school = self.get_school()
        guardian = serializer.validated_data.get(
            "guardian",
            serializer.instance.guardian if serializer.instance else None,
        )
        student = serializer.validated_data.get(
            "student",
            serializer.instance.student if serializer.instance else None,
        )
        if guardian is None or student is None:
            raise ValidationError("الطالب وولي الأمر مطلوبان.")
        if guardian.school_id != school.pk or student.school_id != school.pk:
            raise ValidationError("يجب أن يتبع الطالب وولي الأمر المدرسة النشطة نفسها.")
        ensure_guardian_membership(
            user=guardian.user, school=school, actor=self.request.user,
        )

    @transaction.atomic
    def perform_create(self, serializer):
        self._ensure_verified_guardian(serializer)
        serializer.save(school=self.get_school())

    @transaction.atomic
    def perform_update(self, serializer):
        self._ensure_verified_guardian(serializer)
        serializer.save()


class AcademicYearViewSet(AcademicStructureViewSet):
    serializer_class = AcademicYearSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        return super().get_queryset().order_by("-starts_on")


class AcademicTermViewSet(AcademicStructureViewSet):
    serializer_class = AcademicTermSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        return super().get_queryset().select_related("academic_year").order_by("academic_year__starts_on", "number")


class EducationalStageViewSet(AcademicStructureViewSet):
    serializer_class = EducationalStageSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class GradeLevelViewSet(AcademicStructureViewSet):
    serializer_class = GradeLevelSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("stage")
        stage_id = self.request.query_params.get("stage_id")
        return qs.filter(stage_id=stage_id) if stage_id else qs


class ClassroomViewSet(AcademicStructureViewSet):
    serializer_class = ClassroomSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class SectionViewSet(AcademicStructureViewSet):
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


class SubjectViewSet(AcademicStructureViewSet):
    serializer_class = SubjectSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class PeriodDefinitionViewSet(AcademicStructureViewSet):
    serializer_class = PeriodDefinitionSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES


class SchoolWorkingDayViewSet(AcademicStructureViewSet):
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
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, HR_ADMIN_ROLES, "staff.add_teacher",
        )
        user = get_object_or_404(
            User, pk=self.request.data.get("user_id"),
            is_active=True, status=User.Status.ACTIVE,
        )
        if user.phone_verified_at is None:
            raise ValidationError("يجب توثيق رقم هاتف المعلم قبل إنشاء ملفه الوظيفي.")
        if active_membership(user=user, school=school) is None:
            raise ValidationError("يجب إنشاء عضوية المدرسة للمستخدم قبل إنشاء ملف المعلم.")
        if Teacher.objects.filter(
            school=school, user=user, is_archived=False,
        ).exists():
            raise ValidationError("يوجد بالفعل ملف معلم لهذا الحساب في المدرسة.")
        serializer.save(school=school, user=user)


class TeacherAssignmentViewSet(TenantModelViewSet):
    serializer_class = TeacherAssignmentSerializer
    read_roles = HR_ADMIN_ROLES | ACADEMIC_ADMIN_ROLES | {"teacher"}
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = TeacherAssignment.objects.filter(school=self.get_school(), is_archived=False).select_related("teacher__user", "subject", "section", "academic_year")
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school()):
            teacher = user_teacher_profiles(self.request.user, self.get_school()).filter(is_active_teaching=True).first()
            qs = qs.filter(teacher=teacher) if teacher else qs.none()
        year_id = self.request.query_params.get("academic_year_id")
        return qs.filter(academic_year_id=year_id) if year_id else qs

    def _validate_assignment(self, data):
        school = self.get_school()
        teacher = data["teacher"]
        subject = data["subject"]
        section = data["section"]
        academic_year = data["academic_year"]
        if (
            teacher.school_id != school.pk or teacher.is_archived
            or not teacher.is_active_teaching
        ):
            raise ValidationError({"teacher": "يجب اختيار ملف معلم نشط تابع للمدرسة."})
        if subject.school_id != school.pk or subject.is_archived or not subject.is_active:
            raise ValidationError({"subject": "المادة المحددة غير نشطة أو لا تتبع المدرسة."})
        if (
            section.school_id != school.pk or section.is_archived
            or not section.is_active or section.academic_year_id != academic_year.pk
        ):
            raise ValidationError({"section": "الشعبة غير نشطة أو لا تتبع السنة الدراسية المحددة."})
        if academic_year.school_id != school.pk or academic_year.is_archived:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة أو مؤرشفة."})
        if academic_year.status not in {
            AcademicYear.Status.ACTIVE, AcademicYear.Status.PLANNING,
        }:
            raise ValidationError({"academic_year": "لا يمكن إنشاء إسناد لسنة دراسية مغلقة."})

    def perform_create(self, serializer):
        data = serializer.validated_data
        self._validate_assignment(data)
        serializer.save(school=self.get_school())

    def perform_update(self, serializer):
        data = {
            "teacher": serializer.validated_data.get("teacher", serializer.instance.teacher),
            "subject": serializer.validated_data.get("subject", serializer.instance.subject),
            "section": serializer.validated_data.get("section", serializer.instance.section),
            "academic_year": serializer.validated_data.get("academic_year", serializer.instance.academic_year),
        }
        self._validate_assignment(data)
        serializer.save()


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
                teacher = user_teacher_profiles(self.request.user, school).filter(is_active_teaching=True).first()
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
        teacher = user_teacher_profiles(self.request.user, school).filter(is_active_teaching=True).first()
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

    def perform_update(self, serializer):
        school = self.get_school()
        instance = serializer.instance
        teacher = user_teacher_profiles(self.request.user, school).filter(
            is_active_teaching=True,
        ).first()
        section = serializer.validated_data.get("section", instance.section)
        subject = serializer.validated_data.get("subject", instance.subject)
        if not is_admin(self.request.user, school):
            if not teacher or instance.teacher_id != teacher.pk:
                raise PermissionDenied("لا يمكنك تعديل واجب أسنده معلم آخر.")
            assigned = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, section=section,
                subject=subject, academic_year=section.academic_year,
                is_archived=False,
            ).exists()
            if not assigned:
                raise PermissionDenied("لا يمكنك نقل الواجب إلى مادة أو شعبة غير مسندة إليك.")
        serializer.save(teacher=instance.teacher)
        record_event(
            action="homework.updated",
            description="تم تعديل بيانات الواجب.",
            actor=self.request.user, school=school, obj=instance,
            metadata={"subject_id": str(subject.pk), "section_id": str(section.pk)},
            request=self.request,
        )


class HomeworkSubmissionViewSet(TenantModelViewSet):
    serializer_class = HomeworkSubmissionSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student", "guardian"}
    write_roles = {"student", "teacher"} | ADMIN_ROLES
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "retrieve": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "submit": {"student"},
        "grade": TEACHER_ROLES,
        "request_resubmission": TEACHER_ROLES,
        "attempt_attachment": ADMIN_ROLES | {"teacher", "student", "guardian"},
    }

    def get_queryset(self):
        school = self.get_school()
        qs = HomeworkSubmission.objects.filter(
            school=school, is_archived=False,
        ).select_related("homework", "student", "graded_by").prefetch_related("attempts")
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
                teacher = user_teacher_profiles(self.request.user, school).filter(
                    is_active_teaching=True,
                ).first()
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
        if homework.branch_id and student.branch_id and homework.branch_id != student.branch_id:
            raise PermissionDenied("الواجب لا يخص فرع الطالب.")
        attachment = request.FILES.get("attachment")
        if attachment:
            extension = os.path.splitext(attachment.name)[1].lower()
            if extension not in {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}:
                raise ValidationError({"attachment": "نوع الملف غير مدعوم."})
            if attachment.size > 15 * 1024 * 1024:
                raise ValidationError({"attachment": "الحد الأقصى لحجم المرفق 15 ميجابايت."})

        now = timezone.now()
        late = now > homework.due_date
        attempt_status = (
            HomeworkSubmissionAttempt.Status.LATE
            if late else HomeworkSubmissionAttempt.Status.SUBMITTED
        )
        with transaction.atomic():
            # Lock the homework row as well: the first-ever submission has no
            # existing HomeworkSubmission row to lock yet.
            homework = Homework.objects.select_for_update().get(
                pk=homework.pk, school=school, is_archived=False, is_active=True,
            )
            existing = HomeworkSubmission.objects.select_for_update().filter(
                school=school, homework=homework, student=student,
                is_archived=False,
            ).first()
            created = existing is None
            if existing and existing.status == HomeworkSubmission.Status.GRADED:
                raise ValidationError("تم تصحيح هذا الواجب. لا يمكن إعادة التسليم بعد التصحيح.")
            if existing and existing.status != HomeworkSubmission.Status.RESUBMIT:
                raise ValidationError("لا توجد موافقة من المعلم على إعادة التسليم لهذا الواجب.")
            if created:
                existing = HomeworkSubmission(
                    school=school, branch=homework.branch or student.branch,
                    homework=homework, student=student,
                )
                existing.save()

            next_number = (
                existing.attempts.filter(is_archived=False).aggregate(value=Max("attempt_number"))["value"] or 0
            ) + 1
            attempt = HomeworkSubmissionAttempt(
                school=school,
                branch=existing.branch,
                submission=existing,
                attempt_number=next_number,
                submission_text=request.data.get("submission_text", ""),
                status=attempt_status,
                submitted_at=now,
            )
            if attachment:
                attempt.attachment = attachment
            attempt.save()

            existing.submission_text = attempt.submission_text
            existing.status = (
                HomeworkSubmission.Status.LATE
                if late else HomeworkSubmission.Status.SUBMITTED
            )
            existing.submitted_at = now
            existing.score = None
            existing.graded_by = None
            existing.graded_at = None
            existing.teacher_feedback = ""
            if attempt.attachment:
                existing.attachment.name = attempt.attachment.name
            existing.save(update_fields=[
                "submission_text", "status", "submitted_at", "score",
                "graded_by", "graded_at", "teacher_feedback", "attachment",
                "updated_at",
            ])
            record_event(
                action="homework.submission_attempt_created",
                description="تم حفظ محاولة تسليم واجب دون استبدال المحاولات السابقة.",
                actor=request.user, school=school, obj=attempt,
                metadata={
                    "homework_id": str(homework.pk),
                    "student_id": str(student.pk),
                    "attempt_number": next_number,
                    "late": late,
                },
                request=request,
            )
        existing.refresh_from_db()
        return Response(
            self.get_serializer(existing).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="request-resubmission")
    def request_resubmission(self, request, pk=None):
        school = self.get_school()
        submission = self.get_object()
        teacher = user_teacher_profiles(request.user, school).filter(
            is_active_teaching=True,
        ).first()
        if not is_admin(request.user, school):
            if not teacher or submission.homework.teacher_id != teacher.pk:
                raise PermissionDenied("لا يمكنك طلب إعادة تسليم واجب لا تشرف عليه.")
        if submission.status not in {
            HomeworkSubmission.Status.SUBMITTED,
            HomeworkSubmission.Status.LATE,
        }:
            raise ValidationError("لا يمكن طلب إعادة التسليم إلا بعد وصول محاولة قابلة للمراجعة.")
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "اذكر سبب طلب إعادة التسليم ليظهر للطالب."})
        submission.status = HomeworkSubmission.Status.RESUBMIT
        submission.teacher_feedback = reason[:5000]
        submission.score = None
        submission.graded_by = None
        submission.graded_at = None
        submission.save(update_fields=[
            "status", "teacher_feedback", "score", "graded_by",
            "graded_at", "updated_at",
        ])
        record_event(
            action="homework.resubmission_requested",
            description="طلب المعلم إعادة تسليم الواجب مع حفظ المحاولة السابقة.",
            actor=request.user, school=school, obj=submission,
            metadata={"reason": reason[:500], "homework_id": str(submission.homework_id)},
            request=request,
        )
        return Response(self.get_serializer(submission).data)

    @action(
        detail=True, methods=["get"],
        url_path=r"attempts/(?P<attempt_id>[^/.]+)/attachment",
    )
    def attempt_attachment(self, request, pk=None, attempt_id=None):
        submission = self.get_object()
        attempt = get_object_or_404(
            HomeworkSubmissionAttempt.objects.filter(
                school=self.get_school(), submission=submission,
                is_archived=False,
            ),
            pk=attempt_id,
        )
        if not attempt.attachment:
            raise Http404("لا يوجد مرفق لهذه المحاولة.")
        return FileResponse(
            attempt.attachment.open("rb"),
            as_attachment=True,
            filename=os.path.basename(attempt.attachment.name),
        )

    @action(detail=True, methods=["post"], url_path="grade")
    def grade(self, request, pk=None):
        school = self.get_school()
        with transaction.atomic():
            submission = get_object_or_404(
                HomeworkSubmission.objects.select_for_update().select_related("homework"),
                pk=pk, school=school, is_archived=False,
            )
            teacher = user_teacher_profiles(request.user, school).filter(
                is_active_teaching=True,
            ).first()
            if not is_admin(request.user, school):
                if not teacher or submission.homework.teacher_id != teacher.pk:
                    raise PermissionDenied("لا يمكنك تصحيح تسليم واجب لمعلم آخر.")
            if submission.status not in {
                HomeworkSubmission.Status.SUBMITTED,
                HomeworkSubmission.Status.LATE,
            }:
                raise ValidationError("يجب أن تكون المحاولة مستلمة وغير معلقة لإعادة التسليم قبل التصحيح.")
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
            record_event(
                action="homework.submission_graded",
                description="تم تصحيح محاولة تسليم الواجب.",
                actor=request.user, school=school, obj=submission,
                metadata={"score": str(score), "max_score": str(submission.homework.max_score)},
                request=request,
            )
        return Response(self.get_serializer(submission).data)

    def perform_destroy(self, instance):
        if instance.attempts.filter(is_archived=False).exists():
            raise ValidationError("لا يمكن أرشفة سجل تسليم يحتوي على محاولات تاريخية.")
        raise MethodNotAllowed("DELETE", detail="لا تحذف سجلات تسليم الواجبات؛ استخدم الأرشفة من إجراء إداري معتمد.")


class AssessmentTypeViewSet(TenantModelViewSet):
    serializer_class = AssessmentTypeSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(school=self.get_school())
            try:
                instance.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            instance.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            try:
                instance.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            instance.save()


class GradeBookViewSet(TenantModelViewSet):
    serializer_class = GradeBookSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student", "guardian"}
    write_roles = TEACHER_ROLES
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "retrieve": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "weighted_summary": ADMIN_ROLES | {"teacher", "student", "guardian"},
        "create": TEACHER_ROLES,
        "update": TEACHER_ROLES,
        "partial_update": TEACHER_ROLES,
        "submit_for_approval": TEACHER_ROLES,
        "approve": ACADEMIC_ADMIN_ROLES,
        "publish": ACADEMIC_ADMIN_ROLES,
        "reopen": ACADEMIC_ADMIN_ROLES,
    }

    def get_queryset(self):
        school = self.get_school()
        qs = GradeBook.objects.filter(
            school=school, is_archived=False,
        ).select_related(
            "student", "subject", "academic_term", "assessment_type", "graded_by",
            "submitted_by", "approved_by", "published_by",
        )
        if not is_admin(self.request.user, school):
            allowed = Q(pk__in=[])
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if student:
                    allowed |= Q(
                        student=student,
                        is_published=True,
                        workflow_status=GradeBook.WorkflowStatus.PUBLISHED,
                    )
            if has_school_roles(self.request.user, school, {"guardian"}):
                guardian = user_guardian_profiles(self.request.user, school).first()
                if guardian:
                    allowed |= Q(
                        student__in=guardian.children.filter(
                            school=school, is_archived=False,
                        ),
                        is_published=True,
                        workflow_status=GradeBook.WorkflowStatus.PUBLISHED,
                    )
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).filter(
                    is_active_teaching=True,
                ).first()
                if teacher:
                    assignments = teacher.assignments.filter(
                        school=school, is_archived=False,
                    ).values_list("section_id", "subject_id")
                    for section_id, subject_id in assignments:
                        allowed |= Q(
                            student__section_id=section_id,
                            subject_id=subject_id,
                        )
            qs = qs.filter(allowed)
        term_id = self.request.query_params.get("academic_term_id")
        student_id = self.request.query_params.get("student_id")
        if term_id:
            qs = qs.filter(academic_term_id=term_id)
        if student_id and is_admin(self.request.user, school):
            qs = qs.filter(student_id=student_id)
        status_filter = self.request.query_params.get("workflow_status")
        if status_filter and is_admin(self.request.user, school):
            qs = qs.filter(workflow_status=status_filter)
        return qs.order_by("-graded_at")

    def _assigned_teacher(self, student, subject, academic_year, school):
        teacher = user_teacher_profiles(
            self.request.user, school,
        ).filter(is_active_teaching=True).first()
        if not is_admin(self.request.user, school):
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك في المدرسة المحددة.")
            assigned = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, subject=subject,
                section=student.section, academic_year=academic_year,
                is_archived=False,
            ).exists()
            if not assigned:
                raise PermissionDenied("المادة أو شعبة الطالب غير مسندة إليك.")
        return teacher

    def perform_create(self, serializer):
        school = self.get_school()
        data = serializer.validated_data
        academic_year = (
            data["academic_term"].academic_year
            if data.get("academic_term") else data["student"].academic_year
        )
        teacher = self._assigned_teacher(
            data["student"], data["subject"], academic_year, school,
        )
        with transaction.atomic():
            entry = serializer.save(
                school=school, graded_by=teacher, graded_at=timezone.now(),
                workflow_status=GradeBook.WorkflowStatus.DRAFT,
                is_published=False,
                branch=data["student"].branch,
            )
            try:
                entry.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            entry.save()

    def perform_update(self, serializer):
        entry = serializer.instance
        if entry.workflow_status != GradeBook.WorkflowStatus.DRAFT or entry.is_published:
            raise ValidationError(
                "لا يمكن تعديل درجة مرسلة أو معتمدة أو منشورة مباشرة؛ اطلب إعادة فتحها أولاً."
            )
        data = serializer.validated_data
        student = data.get("student", entry.student)
        subject = data.get("subject", entry.subject)
        term = data.get("academic_term", entry.academic_term)
        academic_year = term.academic_year if term else student.academic_year
        teacher = self._assigned_teacher(student, subject, academic_year, self.get_school())
        with transaction.atomic():
            updated = serializer.save(graded_by=teacher, graded_at=timezone.now())
            try:
                updated.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            updated.save()
        record_event(
            action="gradebook.draft_updated",
            description="تم تعديل درجة ما زالت في حالة المسودة.",
            actor=self.request.user, school=self.get_school(), obj=entry,
            metadata={"student_id": str(student.pk), "subject_id": str(subject.pk)},
            request=self.request,
        )

    def perform_destroy(self, instance):
        if instance.workflow_status != GradeBook.WorkflowStatus.DRAFT or instance.is_published:
            raise ValidationError("لا يمكن أرشفة درجة مرسلة أو معتمدة أو منشورة؛ أعد فتحها واتبع مسار التصحيح.")
        record_event(
            action="gradebook.draft_archived",
            description="تمت أرشفة مسودة درجة غير معتمدة.",
            actor=self.request.user, school=self.get_school(), obj=instance,
            request=self.request,
        )
        super().perform_destroy(instance)

    @action(detail=False, methods=["get"], url_path="weighted-summary")
    def weighted_summary(self, request):
        school = self.get_school()
        student = None
        student_id = request.query_params.get("student_id")
        subject_id = request.query_params.get("subject_id")
        if not subject_id:
            raise ValidationError({"subject_id": "معرف المادة مطلوب."})
        if has_school_roles(request.user, school, {"student"}):
            student = user_student_profiles(request.user, school).first()
            if not student:
                raise PermissionDenied("لا يوجد ملف طالب نشط مرتبط بحسابك.")
        elif has_school_roles(request.user, school, {"guardian"}):
            guardian = user_guardian_profiles(request.user, school).first()
            student = guardian.children.filter(
                pk=student_id, school=school, is_archived=False,
            ).first() if guardian and student_id else None
            if not student:
                raise PermissionDenied("حدد أحد الأبناء المرتبطين بحسابك.")
        else:
            student = get_object_or_404(
                Student, pk=student_id, school=school, is_archived=False,
            ) if student_id else None
            if not is_admin(request.user, school):
                teacher = user_teacher_profiles(request.user, school).filter(
                    is_active_teaching=True,
                ).first()
                if not teacher or not student:
                    raise PermissionDenied("يجب أن يكون الطالب ضمن إسناداتك التدريسية.")
                term_id = request.query_params.get("academic_term_id")
                assignments = teacher.assignments.filter(
                    school=school, section=student.section,
                    subject_id=subject_id, is_archived=False,
                )
                term_id = request.query_params.get("academic_term_id")
                if term_id:
                    assignments = assignments.filter(academic_year_id__in=AcademicTerm.objects.filter(
                        school=school, pk=term_id,
                    ).values_list("academic_year_id", flat=True))
                elif student.academic_year_id:
                    assignments = assignments.filter(academic_year_id=student.academic_year_id)
                if not assignments.exists():
                    raise PermissionDenied("لا يمكنك عرض ملخص درجات طالب خارج المادة أو الشعبة المسندة إليك.")
        if student is None:
            raise ValidationError({"student_id": "معرف الطالب مطلوب لهذا التقرير."})
        entries = GradeBook.objects.filter(
            school=school, student=student, subject_id=subject_id,
            is_archived=False, is_published=True,
            workflow_status=GradeBook.WorkflowStatus.PUBLISHED,
        ).select_related("assessment_type")
        term_id = request.query_params.get("academic_term_id")
        if term_id:
            entries = entries.filter(academic_term_id=term_id)

        grouped = {}
        unweighted = []
        for entry in entries:
            if not entry.assessment_type_id:
                unweighted.append(entry)
                continue
            component = grouped.setdefault(entry.assessment_type_id, {
                "type": entry.assessment_type,
                "score": Decimal("0.00"),
                "max_score": Decimal("0.00"),
                "count": 0,
            })
            component["score"] += entry.score
            component["max_score"] += entry.max_score
            component["count"] += 1

        components = []
        weighted_sum = Decimal("0.00")
        included_weight = Decimal("0.00")
        for component in grouped.values():
            assessment_type = component["type"]
            weight = assessment_type.weight_percentage
            percentage = (
                component["score"] / component["max_score"] * Decimal("100.00")
                if component["max_score"] else Decimal("0.00")
            )
            weighted_sum += percentage * weight
            included_weight += weight
            components.append({
                "assessment_type_id": str(assessment_type.pk),
                "assessment_type": assessment_type.name,
                "weight_percentage": str(weight),
                "average_percentage": str(percentage.quantize(Decimal("0.01"))),
                "weighted_contribution": str(
                    (percentage * weight / Decimal("100.00")).quantize(Decimal("0.01"))
                ),
                "records_count": component["count"],
            })
        weighted_score = (
            weighted_sum / included_weight
            if included_weight else None
        )
        return Response({
            "student_id": str(student.pk),
            "student_name": student.get_full_name(),
            "subject_id": str(subject_id),
            "academic_term_id": str(term_id) if term_id else None,
            "weighted_score_percentage": (
                str(weighted_score.quantize(Decimal("0.01")))
                if weighted_score is not None else None
            ),
            "included_weight_percentage": str(included_weight),
            "components": components,
            "unweighted_records_count": len(unweighted),
        })

    @action(detail=True, methods=["post"], url_path="submit-for-approval")
    def submit_for_approval(self, request, pk=None):
        entry = self.get_object()
        if not is_admin(request.user, self.get_school()):
            teacher = user_teacher_profiles(request.user, self.get_school()).filter(
                is_active_teaching=True,
            ).first()
            if not teacher or entry.graded_by_id != teacher.pk:
                raise PermissionDenied("لا يمكنك إرسال درجة لم تُرصد بواسطة حسابك.")
        if entry.workflow_status != GradeBook.WorkflowStatus.DRAFT:
            raise ValidationError("لا يمكن إرسال الدرجة للمراجعة إلا من حالة المسودة.")
        entry.workflow_status = GradeBook.WorkflowStatus.SUBMITTED
        entry.submitted_by = request.user
        entry.submitted_at = timezone.now()
        entry.approved_by = None
        entry.approved_at = None
        entry.published_by = None
        entry.published_at = None
        entry.is_published = False
        entry.save(update_fields=[
            "workflow_status", "submitted_by", "submitted_at", "approved_by",
            "approved_at", "published_by", "published_at", "is_published",
            "updated_at",
        ])
        record_event(
            action="gradebook.submitted_for_approval",
            description="أرسلت الدرجة للمراجعة والاعتماد.",
            actor=request.user, school=self.get_school(), obj=entry, request=request,
        )
        return Response(self.get_serializer(entry).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        entry = self.get_object()
        if entry.workflow_status != GradeBook.WorkflowStatus.SUBMITTED:
            raise ValidationError("لا يعتمد إلا سجل أرسل للمراجعة.")
        entry.workflow_status = GradeBook.WorkflowStatus.APPROVED
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.save(update_fields=[
            "workflow_status", "approved_by", "approved_at", "updated_at",
        ])
        record_event(
            action="gradebook.approved",
            description="تم اعتماد الدرجة قبل نشرها.",
            actor=request.user, school=self.get_school(), obj=entry, request=request,
        )
        return Response(self.get_serializer(entry).data)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        entry = self.get_object()
        publish = request.data.get("is_published", True)
        if not isinstance(publish, bool):
            raise ValidationError({"is_published": "أرسل قيمة منطقية true أو false."})
        if publish:
            if entry.workflow_status == GradeBook.WorkflowStatus.PUBLISHED and entry.is_published:
                return Response({"id": str(entry.pk), "is_published": True})
            if entry.workflow_status != GradeBook.WorkflowStatus.APPROVED:
                raise ValidationError("يجب اعتماد الدرجة قبل نشرها.")
            entry.workflow_status = GradeBook.WorkflowStatus.PUBLISHED
            entry.is_published = True
            entry.published_by = request.user
            entry.published_at = timezone.now()
            action_name = "gradebook.published"
            description = "تم نشر الدرجة بعد اعتمادها."
            metadata = {}
        else:
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise ValidationError({"reason": "سبب إخفاء الدرجة مطلوب للتدقيق."})
            if entry.workflow_status != GradeBook.WorkflowStatus.PUBLISHED or not entry.is_published:
                raise ValidationError("الدرجة ليست منشورة حالياً.")
            entry.workflow_status = GradeBook.WorkflowStatus.APPROVED
            entry.is_published = False
            entry.published_by = None
            entry.published_at = None
            action_name = "gradebook.unpublished"
            description = "تم إخفاء الدرجة المنشورة."
            metadata = {"reason": reason[:500]}
        entry.save(update_fields=[
            "workflow_status", "is_published", "published_by",
            "published_at", "updated_at",
        ])
        record_event(
            action=action_name, description=description,
            actor=request.user, school=self.get_school(), obj=entry,
            metadata=metadata, request=request,
        )
        return Response({
            "id": str(entry.pk), "workflow_status": entry.workflow_status,
            "is_published": entry.is_published,
        })

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        entry = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "سبب إعادة فتح الدرجة مطلوب."})
        if entry.workflow_status not in {
            GradeBook.WorkflowStatus.APPROVED,
            GradeBook.WorkflowStatus.PUBLISHED,
        }:
            raise ValidationError("يمكن إعادة فتح الدرجة المعتمدة أو المنشورة فقط.")
        entry.workflow_status = GradeBook.WorkflowStatus.DRAFT
        entry.is_published = False
        entry.revision_reason = reason[:500]
        entry.submitted_by = None
        entry.submitted_at = None
        entry.approved_by = None
        entry.approved_at = None
        entry.published_by = None
        entry.published_at = None
        entry.save(update_fields=[
            "workflow_status", "is_published", "revision_reason",
            "submitted_by", "submitted_at", "approved_by", "approved_at",
            "published_by", "published_at", "updated_at",
        ])
        record_event(
            action="gradebook.reopened",
            description="أعيد فتح درجة سبق اعتمادها أو نشرها للتصحيح.",
            actor=request.user, school=self.get_school(), obj=entry,
            metadata={"reason": reason[:500]}, request=request,
        )
        return Response(self.get_serializer(entry).data)


class QuestionBankViewSet(TenantModelViewSet):
    serializer_class = QuestionBankTeacherSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}
    write_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}

    def get_queryset(self):
        school = self.get_school()
        qs = QuestionBank.objects.filter(
            school=school, is_archived=False,
        ).select_related("subject", "grade_level", "created_by")
        if has_school_roles(self.request.user, school, {"teacher"}) and not is_admin(
            self.request.user, school,
        ):
            teacher = user_teacher_profiles(self.request.user, school).filter(
                is_active_teaching=True,
            ).first()
            if teacher is None:
                return qs.none()
            allowed_questions = Q(created_by=self.request.user)
            assignments = teacher.assignments.filter(
                school=school, is_archived=False,
            ).values_list("section__grade_id", "subject_id")
            for grade_id, assigned_subject_id in assignments:
                allowed_questions |= Q(
                    grade_level_id=grade_id,
                    subject_id=assigned_subject_id,
                )
            qs = qs.filter(allowed_questions)
        subject_id = self.request.query_params.get("subject_id")
        grade_id = self.request.query_params.get("grade_level_id")
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).filter(is_active_teaching=True).first()
        data = serializer.validated_data
        if not is_admin(self.request.user, school):
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك في المدرسة المحددة.")
            assignments = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, subject=data["subject"],
                is_archived=False,
            )
            if data.get("grade_level"):
                assignments = assignments.filter(section__grade=data["grade_level"])
            if not assignments.exists():
                raise PermissionDenied("لا يمكنك إضافة سؤال لمادة أو صف غير مسند إليك.")
        candidate = QuestionBank(
            **data,
            school=school,
            created_by=self.request.user,
        )
        try:
            candidate.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        serializer.save(school=school, created_by=self.request.user)

    def perform_update(self, serializer):
        school = self.get_school()
        question = serializer.instance
        teacher = user_teacher_profiles(self.request.user, school).filter(
            is_active_teaching=True,
        ).first()
        if not is_admin(self.request.user, school):
            if not teacher or question.created_by_id != self.request.user.pk:
                raise PermissionDenied("يمكن للمعلم تعديل الأسئلة التي أنشأها بنفسه فقط.")
        if question.included_in_exams.filter(
            Q(is_published=True) | Q(submissions__is_archived=False),
            is_archived=False,
        ).distinct().exists():
            raise ValidationError("لا يمكن تعديل سؤال مرتبط باختبار منشور أو بدأت له محاولات.")
        data = serializer.validated_data
        subject = data.get("subject", question.subject)
        grade_level = data.get("grade_level", question.grade_level)
        if not is_admin(self.request.user, school):
            assigned = teacher.assignments.filter(
                school=school, subject=subject, is_archived=False,
            )
            if grade_level:
                assigned = assigned.filter(section__grade=grade_level)
            if not assigned.exists():
                raise PermissionDenied("لا يمكنك نقل السؤال إلى مادة أو صف غير مسند إليك.")
        with transaction.atomic():
            updated = serializer.save()
            try:
                updated.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            updated.save()
        record_event(
            action="assessment.question_updated",
            description="تم تعديل سؤال من بنك الأسئلة.",
            actor=self.request.user, school=school, obj=updated,
            metadata={"subject_id": str(updated.subject_id)},
            request=self.request,
        )

    def perform_destroy(self, instance):
        if instance.included_in_exams.exists():
            raise ValidationError("لا يمكن أرشفة سؤال مرتبط باختبار؛ احتفظ به كسجل تاريخي.")
        record_event(
            action="assessment.question_archived",
            description="تمت أرشفة سؤال غير مستخدم في أي اختبار.",
            actor=self.request.user, school=self.get_school(), obj=instance,
            request=self.request,
        )
        super().perform_destroy(instance)


class OnlineExamViewSet(TenantModelViewSet):
    serializer_class = OnlineExamSerializer
    read_roles = ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}
    action_role_map = {
        "list": ADMIN_ROLES | {"teacher", "student"},
        "retrieve": ADMIN_ROLES | {"teacher", "student"},
        "paper": {"student"} | ADMIN_ROLES,
        "start": {"student"},
        "submit": {"student"},
        "publish": ACADEMIC_ADMIN_ROLES,
        "report": ACADEMIC_ADMIN_ROLES,
    }

    def get_queryset(self):
        school = self.get_school()
        qs = OnlineExam.objects.filter(
            school=school, is_archived=False,
        ).select_related("subject", "academic_term", "grade_level", "section")
        if not is_admin(self.request.user, school):
            allowed = Q(pk__in=[])
            if has_school_roles(self.request.user, school, {"student"}):
                student = user_student_profiles(self.request.user, school).first()
                if student:
                    allowed |= (
                        Q(is_published=True)
                        & (
                            Q(section=student.section)
                            | Q(section__isnull=True, grade_level=student.grade_level)
                        )
                    )
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).filter(
                    is_active_teaching=True,
                ).first()
                if teacher:
                    allowed |= Q(created_by=self.request.user)
                    assignments = teacher.assignments.filter(
                        school=school, is_archived=False,
                    ).values_list("section_id", "section__grade_id", "subject_id")
                    for section_id, grade_id, subject_id in assignments:
                        allowed |= Q(
                            section_id=section_id, subject_id=subject_id,
                        ) | Q(
                            section__isnull=True,
                            grade_level_id=grade_id,
                            subject_id=subject_id,
                        )
            qs = qs.filter(allowed)
        return qs.order_by("-start_time")

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).filter(
            is_active_teaching=True,
        ).first()
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
        if data["duration_minutes"] < 1:
            raise ValidationError({"duration_minutes": "مدة الاختبار يجب أن تكون دقيقة واحدة على الأقل."})
        questions = list(data.get("questions", []))
        question_total = sum((q.default_marks for q in questions), Decimal("0.00"))
        if question_total > data["total_marks"]:
            raise ValidationError({"questions": "مجموع درجات الأسئلة يتجاوز الدرجة العظمى للاختبار."})
        if any(q.school_id != school.pk for q in questions):
            raise ValidationError({"questions": "يجب أن تنتمي كل أسئلة الاختبار إلى المدرسة النشطة."})
        if any(q.subject_id != data["subject"].pk for q in questions):
            raise ValidationError({"questions": "يجب أن تنتمي كل أسئلة الاختبار إلى المادة المختارة."})
        if not is_admin(self.request.user, school):
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك في المدرسة المحددة.")
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
        with transaction.atomic():
            exam = serializer.save(
                school=school, created_by=self.request.user, is_published=False,
                published_by=None, published_at=None,
            )
            try:
                exam.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            exam.save()

    def perform_update(self, serializer):
        exam = serializer.instance
        school = self.get_school()
        if exam.is_published:
            raise ValidationError("ألغ نشر الاختبار أولاً قبل تعديل بياناته.")
        if exam.submissions.filter(is_archived=False).exists():
            raise ValidationError("لا يمكن تعديل اختبار بعد بدء أي محاولة؛ أنشئ نسخة جديدة.")
        data = serializer.validated_data
        subject = data.get("subject", exam.subject)
        academic_term = data.get("academic_term", exam.academic_term)
        grade_level = data.get("grade_level", exam.grade_level)
        section = data.get("section", exam.section)
        duration_minutes = data.get("duration_minutes", exam.duration_minutes)
        total_marks = data.get("total_marks", exam.total_marks)
        passing_marks = data.get("passing_marks", exam.passing_marks)
        start_time = data.get("start_time", exam.start_time)
        end_time = data.get("end_time", exam.end_time)
        questions = list(data.get("questions", exam.questions.all()))
        if end_time <= start_time or duration_minutes < 1 or passing_marks > total_marks:
            raise ValidationError("بيانات التوقيت أو المدة أو درجات النجاح للاختبار غير صالحة.")
        if section and (
            section.school_id != school.pk or section.grade_id != grade_level.pk
            or section.academic_year_id != academic_term.academic_year_id
        ):
            raise ValidationError({"section": "الشعبة يجب أن تتبع المدرسة والصف والسنة المحددة للاختبار."})
        if any(question.school_id != school.pk or question.subject_id != subject.pk for question in questions):
            raise ValidationError({"questions": "أسئلة الاختبار يجب أن تتبع المدرسة والمادة المختارة."})
        if sum((question.default_marks for question in questions), Decimal("0.00")) > total_marks:
            raise ValidationError({"questions": "مجموع درجات الأسئلة يتجاوز الدرجة العظمى للاختبار."})
        teacher = user_teacher_profiles(self.request.user, school).filter(
            is_active_teaching=True,
        ).first()
        if not is_admin(self.request.user, school):
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك.")
            academic_year = data.get("academic_term", exam.academic_term).academic_year
            subject = data.get("subject", exam.subject)
            section = data.get("section", exam.section)
            grade_level = data.get("grade_level", exam.grade_level)
            assigned = teacher.assignments.filter(
                school=self.get_school(), subject=subject,
                academic_year=academic_year, is_archived=False,
            )
            if section:
                assigned = assigned.filter(section=section)
            else:
                assigned = assigned.filter(section__grade=grade_level)
            if not assigned.exists():
                raise PermissionDenied("لا يمكنك تعديل اختبار خارج المواد والشعب المسندة إليك.")
        with transaction.atomic():
            updated = serializer.save(is_published=False)
            try:
                updated.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            updated.save()

    def perform_destroy(self, instance):
        if instance.is_published or instance.submissions.filter(is_archived=False).exists():
            raise ValidationError("لا يمكن أرشفة اختبار منشور أو لديه محاولات؛ ألغ نشره واحتفظ بسجله.")
        super().perform_destroy(instance)

    def _student_can_take_exam(self, student, exam):
        if not student or not exam.is_published:
            return False
        if exam.section_id:
            return exam.section_id == student.section_id
        return exam.grade_level_id == student.grade_level_id

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        exam = self.get_object()
        publish = request.data.get("is_published", True)
        if not isinstance(publish, bool):
            raise ValidationError({"is_published": "أرسل قيمة منطقية true أو false."})
        if publish:
            if exam.is_published:
                return Response({"id": str(exam.pk), "is_published": True})
            if not exam.questions.exists():
                raise ValidationError({"questions": "أضف سؤالاً واحداً على الأقل قبل نشر الاختبار."})
            if exam.end_time <= exam.start_time or exam.passing_marks > exam.total_marks:
                raise ValidationError("بيانات التوقيت أو درجات النجاح للاختبار غير صالحة.")
            if exam.questions.exclude(school_id=exam.school_id).exists():
                raise ValidationError({"questions": "يوجد سؤال لا يتبع المدرسة نفسها."})
            if exam.questions.exclude(subject_id=exam.subject_id).exists():
                raise ValidationError({"questions": "يوجد سؤال من مادة مختلفة عن مادة الاختبار."})
            if sum((question.default_marks for question in exam.questions.all()), Decimal("0.00")) > exam.total_marks:
                raise ValidationError({"questions": "مجموع درجات أسئلة الاختبار يتجاوز الدرجة العظمى."})
            exam.is_published = True
            exam.published_by = request.user
            exam.published_at = timezone.now()
            exam.unpublished_reason = ""
            action_name = "assessment.exam_published"
            description = "تم نشر الاختبار للطلاب بعد مراجعة بياناته وأسئلته."
            metadata = {}
        else:
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise ValidationError({"reason": "سبب إلغاء نشر الاختبار مطلوب."})
            if not exam.is_published:
                return Response({"id": str(exam.pk), "is_published": False})
            if exam.submissions.filter(
                status=StudentOnlineExamSubmission.Status.IN_PROGRESS,
                is_archived=False,
            ).exists():
                raise ValidationError("لا يمكن إلغاء نشر الاختبار أثناء وجود محاولات جارية.")
            exam.is_published = False
            exam.published_by = None
            exam.published_at = None
            exam.unpublished_reason = reason[:500]
            action_name = "assessment.exam_unpublished"
            description = "تم إلغاء نشر الاختبار مع تسجيل السبب."
            metadata = {"reason": reason[:500]}
        exam.save(update_fields=[
            "is_published", "published_by", "published_at",
            "unpublished_reason", "updated_at",
        ])
        record_event(
            action=action_name, description=description,
            actor=request.user, school=self.get_school(), obj=exam,
            metadata=metadata, request=request,
        )
        return Response({"id": str(exam.pk), "is_published": exam.is_published})

    @action(detail=True, methods=["get"], url_path="paper")
    def paper(self, request, pk=None):
        exam = self.get_object()
        student = user_student_profiles(request.user, self.get_school()).first()
        if not has_school_roles(request.user, self.get_school(), {"student"}) and not is_admin(
            request.user, self.get_school(),
        ):
            raise PermissionDenied("ورقة الاختبار متاحة للطالب المستهدف فقط.")
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
        if not has_school_roles(request.user, self.get_school(), {"student"}):
            raise PermissionDenied("بدء الاختبار متاح للطالب فقط.")
        if not self._student_can_take_exam(student, exam):
            raise PermissionDenied("هذا الاختبار غير متاح لحسابك.")
        now = timezone.now()
        if now < exam.start_time or now > exam.end_time:
            raise ValidationError("لا يمكن بدء الاختبار خارج الوقت المحدد.")
        with transaction.atomic():
            locked_exam = OnlineExam.objects.select_for_update().get(
                pk=exam.pk, school=self.get_school(), is_archived=False,
            )
            submission, created = StudentOnlineExamSubmission.objects.get_or_create(
                school=self.get_school(), exam=locked_exam, student=student,
                defaults={
                    "branch": exam.branch or student.branch,
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
            "reconnected": not created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        exam = self.get_object()
        student = user_student_profiles(request.user, self.get_school()).first()
        if not has_school_roles(request.user, self.get_school(), {"student"}):
            raise PermissionDenied("تسليم الاختبار متاح للطالب فقط.")
        if not student or (
            exam.section_id and exam.section_id != student.section_id
        ) or (
            not exam.section_id and exam.grade_level_id != student.grade_level_id
        ):
            raise PermissionDenied("تسليم الاختبار متاح للطالب المستهدف فقط.")
        answers = request.data.get("answers")
        if not isinstance(answers, dict):
            raise ValidationError({"answers": "أرسل الإجابات ككائن JSON: question_id -> answer."})
        allowed_questions = list(exam.questions.all())
        question_map = {str(question.pk): question for question in allowed_questions}
        if set(answers) - set(question_map):
            raise ValidationError({"answers": "تتضمن الإجابات سؤالاً لا ينتمي لهذا الاختبار."})
        for question_id, answer in answers.items():
            question = question_map[question_id]
            if question.question_type == QuestionBank.QuestionType.MCQ:
                valid_options = {
                    str(option.get("id", "")).strip()
                    for option in question.options_json
                    if isinstance(option, dict) and option.get("id") is not None
                }
                if str(answer).strip() not in valid_options:
                    raise ValidationError({"answers": f"اختيار غير صالح للسؤال {question_id}."})
            elif question.question_type == QuestionBank.QuestionType.TRUE_FALSE:
                if str(answer).strip().lower() not in {"true", "false", "صح", "خطأ"}:
                    raise ValidationError({"answers": f"إجابة الصح والخطأ غير صالحة للسؤال {question_id}."})
            elif not isinstance(answer, (str, int, float)):
                raise ValidationError({"answers": f"صيغة الإجابة غير صالحة للسؤال {question_id}."})

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
            if now > deadline:
                raise ValidationError("انتهت مهلة الاختبار؛ لا يمكن قبول الإجابات بعد الوقت المحدد.")
            submission.submitted_at = now
            submission.answers_json = answers
            submission.status = StudentOnlineExamSubmission.Status.SUBMITTED
            submission.auto_score = Decimal("0.00")
            for question in allowed_questions:
                if question.question_type in {
                    QuestionBank.QuestionType.MCQ,
                    QuestionBank.QuestionType.TRUE_FALSE,
                }:
                    student_answer = str(answers.get(str(question.pk), "")).strip().lower()
                    correct_answer = str(question.correct_answer).strip().lower()
                    if question.question_type == QuestionBank.QuestionType.TRUE_FALSE:
                        student_answer = "true" if student_answer in {"true", "صح"} else "false"
                        correct_answer = "true" if correct_answer in {"true", "صح"} else "false"
                    if student_answer and student_answer == correct_answer:
                        submission.auto_score += question.default_marks
            if submission.auto_score > exam.total_marks:
                raise ValidationError("مجموع درجات الأسئلة الموضوعية يتجاوز الدرجة العظمى للاختبار.")
            submission.final_score = submission.auto_score
            submission.result_published = False
            submission.result_published_at = None
            submission.result_published_by = None
            submission.save(update_fields=[
                "answers_json", "submitted_at", "status", "auto_score",
                "final_score", "result_published", "result_published_at",
                "result_published_by", "updated_at",
            ])
            record_event(
                action="assessment.exam_submitted",
                description="سلّم الطالب إجاباته وتم حفظها واحتساب الجزء الموضوعي.",
                actor=request.user, school=self.get_school(), obj=submission,
                metadata={"exam_id": str(exam.pk), "auto_score": str(submission.auto_score)},
                request=request,
            )
        return Response({
            "submission_id": str(submission.pk),
            "status": submission.status,
            "submitted_at": submission.submitted_at,
            "result_published": False,
        })

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        exam = self.get_object()
        attempts = exam.submissions.filter(is_archived=False)
        published = attempts.filter(result_published=True)
        average = published.aggregate(value=Sum("final_score"))["value"]
        completed = attempts.exclude(status=StudentOnlineExamSubmission.Status.IN_PROGRESS).count()
        if exam.section_id:
            target_students = Student.objects.filter(
                school=exam.school, section_id=exam.section_id,
                academic_year=exam.academic_term.academic_year,
                is_archived=False,
            ).count()
        else:
            target_students = Student.objects.filter(
                school=exam.school, grade_level_id=exam.grade_level_id,
                academic_year=exam.academic_term.academic_year,
                is_archived=False,
            ).count()
        return Response({
            "exam_id": str(exam.pk),
            "target_students": target_students,
            "started": attempts.count(),
            "completed": completed,
            "in_progress": attempts.filter(status=StudentOnlineExamSubmission.Status.IN_PROGRESS).count(),
            "graded": attempts.filter(status=StudentOnlineExamSubmission.Status.GRADED).count(),
            "published_results": published.count(),
            "average_published_score": str(
                (average / published.count()).quantize(Decimal("0.01"))
            ) if published.exists() and average is not None else None,
            "unstarted": max(target_students - attempts.count(), 0),
        })


class ExamSubmissionViewSet(TenantModelViewSet):
    serializer_class = ExamSubmissionReviewSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher", "student", "guardian"}
    write_roles = ACADEMIC_ADMIN_ROLES
    action_role_map = {
        "list": ACADEMIC_ADMIN_ROLES | {"teacher", "student", "guardian"},
        "retrieve": ACADEMIC_ADMIN_ROLES | {"teacher", "student", "guardian"},
        "grade": ACADEMIC_ADMIN_ROLES | {"teacher"},
        "publish": ACADEMIC_ADMIN_ROLES,
        "reopen": ACADEMIC_ADMIN_ROLES,
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
            if has_school_roles(self.request.user, school, {"guardian"}):
                guardian = user_guardian_profiles(self.request.user, school).first()
                if guardian:
                    allowed |= Q(
                        student__in=guardian.children.filter(school=school, is_archived=False),
                        result_published=True,
                    )
            if has_school_roles(self.request.user, school, {"teacher"}):
                teacher = user_teacher_profiles(self.request.user, school).filter(
                    is_active_teaching=True,
                ).first()
                if teacher:
                    assignments = teacher.assignments.filter(
                        school=school, is_archived=False,
                    ).values_list("section_id", "section__grade_id", "subject_id", "academic_year_id")
                    for section_id, grade_id, subject_id, year_id in assignments:
                        allowed |= Q(
                            exam__section_id=section_id, exam__subject_id=subject_id,
                            exam__academic_term__academic_year_id=year_id,
                        ) | Q(
                            exam__section__isnull=True,
                            exam__grade_level_id=grade_id,
                            exam__subject_id=subject_id,
                            exam__academic_term__academic_year_id=year_id,
                        )
            qs = qs.filter(allowed)
        return qs.order_by("-submitted_at")

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="تنشأ محاولة الاختبار من خلال POST /online-exams/{id}/start/.")

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT", detail="لا تعدّل إجابات أو نتائج محاولة الاختبار مباشرة؛ استخدم إجراءات التصحيح وإعادة الفتح.")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH", detail="لا تعدّل إجابات أو نتائج محاولة الاختبار مباشرة؛ استخدم إجراءات التصحيح وإعادة الفتح.")

    def perform_destroy(self, instance):
        raise ValidationError("محاولات الاختبار سجلات تاريخية لا تحذف بعد بدئها.")

    @action(detail=True, methods=["post"], url_path="grade")
    def grade(self, request, pk=None):
        school = self.get_school()
        with transaction.atomic():
            submission = get_object_or_404(
                StudentOnlineExamSubmission.objects.select_for_update().select_related("exam"),
                pk=pk, school=school, is_archived=False,
            )
            teacher = user_teacher_profiles(request.user, school).filter(
                is_active_teaching=True,
            ).first()
            if not is_admin(request.user, school):
                if not teacher:
                    raise PermissionDenied("يجب ربط حسابك بملف معلم.")
                assigned = teacher.assignments.filter(
                    school=school, subject=submission.exam.subject,
                    academic_year=submission.exam.academic_term.academic_year,
                    is_archived=False,
                )
                if submission.exam.section_id:
                    assigned = assigned.filter(section_id=submission.exam.section_id)
                else:
                    assigned = assigned.filter(section__grade_id=submission.exam.grade_level_id)
                if not assigned.exists():
                    raise PermissionDenied("لا يمكنك تصحيح اختبار غير مسند إليك.")
            if submission.status != StudentOnlineExamSubmission.Status.SUBMITTED:
                raise ValidationError("لا يمكن تصحيح إلا محاولة لم تُصحح بعد؛ استخدم إعادة الفتح لإعادة التصحيح.")
            try:
                manual_score = Decimal(str(request.data.get("manual_score", "0")))
            except Exception:
                raise ValidationError({"manual_score": "الدرجة المقالية غير صحيحة."})
            manual_max = sum(
                (
                    question.default_marks for question in submission.exam.questions.all()
                    if question.question_type in {
                        QuestionBank.QuestionType.SHORT_ANSWER,
                        QuestionBank.QuestionType.ESSAY,
                    }
                ),
                Decimal("0.00"),
            )
            if manual_score < 0 or manual_score > manual_max:
                raise ValidationError({
                    "manual_score": f"درجة الأسئلة المقالية/القصيرة يجب أن تكون بين صفر و {manual_max}.",
                })
            if submission.auto_score + manual_score > submission.exam.total_marks:
                raise ValidationError({"manual_score": "إجمالي الدرجة يتجاوز الدرجة العظمى للاختبار."})
            submission.manual_score = manual_score
            submission.final_score = submission.auto_score + manual_score
            submission.teacher_feedback = request.data.get("teacher_feedback", "")
            submission.graded_by = request.user
            submission.status = StudentOnlineExamSubmission.Status.GRADED
            submission.result_published = False
            submission.result_published_at = None
            submission.result_published_by = None
            submission.save(update_fields=[
                "manual_score", "final_score", "teacher_feedback", "graded_by",
                "status", "result_published", "result_published_at",
                "result_published_by", "updated_at",
            ])
            record_event(
                action="assessment.exam_submission_graded",
                description="تم تصحيح محاولة الاختبار ولم تُنشر النتيجة بعد.",
                actor=request.user, school=school, obj=submission,
                metadata={
                    "auto_score": str(submission.auto_score),
                    "manual_score": str(manual_score),
                    "final_score": str(submission.final_score),
                },
                request=request,
            )
        return Response({
            "id": str(submission.pk), "status": submission.status,
            "auto_score": str(submission.auto_score),
            "manual_score": str(submission.manual_score),
            "final_score": str(submission.final_score),
            "result_published": False,
        })

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        submission = self.get_object()
        publish = request.data.get("is_published", True)
        if not isinstance(publish, bool):
            raise ValidationError({"is_published": "أرسل قيمة منطقية true أو false."})
        if publish:
            if submission.status != StudentOnlineExamSubmission.Status.GRADED:
                raise ValidationError("يجب تصحيح المحاولة قبل نشر نتيجتها.")
            submission.result_published = True
            submission.result_published_at = timezone.now()
            submission.result_published_by = request.user
            submission.result_revision_reason = ""
            action_name = "assessment.exam_result_published"
            description = "تم نشر نتيجة الاختبار للطالب وولي الأمر."
            metadata = {}
        else:
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise ValidationError({"reason": "سبب إخفاء النتيجة مطلوب للتدقيق."})
            if not submission.result_published:
                return Response({"id": str(submission.pk), "result_published": False})
            submission.result_published = False
            submission.result_published_at = None
            submission.result_published_by = None
            submission.result_revision_reason = reason[:500]
            action_name = "assessment.exam_result_unpublished"
            description = "تم إخفاء نتيجة منشورة مع تسجيل السبب."
            metadata = {"reason": reason[:500]}
        submission.save(update_fields=[
            "result_published", "result_published_at", "result_published_by",
            "result_revision_reason", "updated_at",
        ])
        record_event(
            action=action_name, description=description,
            actor=request.user, school=self.get_school(), obj=submission,
            metadata=metadata, request=request,
        )
        return Response({
            "id": str(submission.pk),
            "result_published": submission.result_published,
            "result_published_at": submission.result_published_at,
        })

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        submission = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "سبب إعادة فتح النتيجة مطلوب."})
        if submission.status != StudentOnlineExamSubmission.Status.GRADED:
            raise ValidationError("يمكن إعادة فتح محاولة مصححة فقط.")
        submission.status = StudentOnlineExamSubmission.Status.SUBMITTED
        submission.result_published = False
        submission.result_published_at = None
        submission.result_published_by = None
        submission.result_revision_reason = reason[:500]
        submission.manual_score = Decimal("0.00")
        submission.final_score = submission.auto_score
        submission.graded_by = None
        submission.teacher_feedback = ""
        submission.save(update_fields=[
            "status", "result_published", "result_published_at",
            "result_published_by", "result_revision_reason", "manual_score",
            "final_score", "graded_by", "teacher_feedback", "updated_at",
        ])
        record_event(
            action="assessment.exam_result_reopened",
            description="أعيد فتح نتيجة اختبار للتصحيح بعد تسجيل السبب.",
            actor=request.user, school=self.get_school(), obj=submission,
            metadata={"reason": reason[:500]}, request=request,
        )
        return Response({"id": str(submission.pk), "status": submission.status})


class ExamCommitteeViewSet(TenantModelViewSet):
    serializer_class = ExamCommitteeSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES

    def _validate_head_supervisor(self, supervisor, branch, school):
        if supervisor is None:
            return
        if supervisor.school_id != school.pk or supervisor.is_archived or not supervisor.is_active_teaching:
            raise ValidationError({"head_supervisor": "رئيس اللجنة يجب أن يكون معلماً نشطاً في المدرسة نفسها."})
        if branch and supervisor.branch_id and branch.pk != supervisor.branch_id:
            raise ValidationError({"head_supervisor": "رئيس اللجنة يتبع فرعاً مختلفاً."})

    def perform_create(self, serializer):
        school = self.get_school()
        data = serializer.validated_data
        branch = data.get("branch")
        supervisor = data.get("head_supervisor")
        self._validate_head_supervisor(supervisor, branch, school)
        with transaction.atomic():
            committee = serializer.save(school=school)
            try:
                committee.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            committee.save()
        record_event(
            action="assessment.exam_committee_created",
            description="تم إنشاء لجنة اختبار.",
            actor=self.request.user, school=school, obj=committee, request=self.request,
        )

    def perform_update(self, serializer):
        school = self.get_school()
        data = serializer.validated_data
        branch = data.get("branch", serializer.instance.branch)
        supervisor = data.get("head_supervisor", serializer.instance.head_supervisor)
        self._validate_head_supervisor(supervisor, branch, school)
        with transaction.atomic():
            committee = serializer.save()
            try:
                committee.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            committee.save()
        record_event(
            action="assessment.exam_committee_updated",
            description="تم تعديل لجنة اختبار.",
            actor=self.request.user, school=school, obj=committee, request=self.request,
        )

    def perform_destroy(self, instance):
        if instance.seatings.filter(is_archived=False).exists():
            raise ValidationError("لا يمكن أرشفة لجنة لديها أرقام جلوس؛ احتفظ بسجلها.")
        record_event(
            action="assessment.exam_committee_archived",
            description="تمت أرشفة لجنة اختبار لا تحتوي على أرقام جلوس.",
            actor=self.request.user, school=self.get_school(), obj=instance,
            request=self.request,
        )
        super().perform_destroy(instance)

    def get_queryset(self):
        qs = super().get_queryset()
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(
            self.request.user, self.get_school(),
        ):
            teacher = user_teacher_profiles(self.request.user, self.get_school()).filter(
                is_active_teaching=True,
            ).first()
            if teacher:
                qs = qs.filter(
                    Q(head_supervisor=teacher)
                    | Q(proctor_assignments__teacher=teacher, proctor_assignments__is_archived=False)
                ).distinct()
            else:
                qs = qs.none()
        elif has_school_roles(self.request.user, self.get_school(), {"student"}) and not is_admin(
            self.request.user, self.get_school(),
        ):
            student = user_student_profiles(self.request.user, self.get_school()).first()
            qs = qs.filter(seatings__student=student).distinct() if student else qs.none()
        return qs


class ExamCommitteeProctorViewSet(TenantModelViewSet):
    serializer_class = ExamCommitteeProctorSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher"}
    write_roles = ACADEMIC_ADMIN_ROLES
    action_role_map = {
        "list": ACADEMIC_ADMIN_ROLES | {"teacher"},
        "retrieve": ACADEMIC_ADMIN_ROLES | {"teacher"},
        "create": ACADEMIC_ADMIN_ROLES,
        "update": ACADEMIC_ADMIN_ROLES,
        "partial_update": ACADEMIC_ADMIN_ROLES,
        "destroy": ACADEMIC_ADMIN_ROLES,
    }

    def get_queryset(self):
        qs = super().get_queryset().select_related("committee", "teacher", "teacher__user")
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(
            self.request.user, self.get_school(),
        ):
            teacher = user_teacher_profiles(self.request.user, self.get_school()).filter(
                is_active_teaching=True,
            ).first()
            qs = qs.filter(teacher=teacher) if teacher else qs.none()
        return qs

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = serializer.validated_data["teacher"]
        committee = serializer.validated_data["committee"]
        if teacher.school_id != school.pk or committee.school_id != school.pk:
            raise ValidationError("المعلم واللجنة يجب أن يتبعا المدرسة النشطة.")
        if not teacher.is_active_teaching or teacher.is_archived:
            raise ValidationError({"teacher": "لا يمكن تكليف معلم غير نشط أو مؤرشف."})
        if committee.branch_id and teacher.branch_id and committee.branch_id != teacher.branch_id:
            raise ValidationError({"teacher": "المعلم يتبع فرعاً مختلفاً عن اللجنة."})
        with transaction.atomic():
            assignment = serializer.save(
                school=school, branch=committee.branch,
                assigned_by=self.request.user, assigned_at=timezone.now(),
            )
            try:
                assignment.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            assignment.save()
        record_event(
            action="assessment.exam_proctor_assigned",
            description="تم تكليف معلم بمراقبة لجنة اختبار.",
            actor=self.request.user, school=school,
            obj=serializer.instance,
            metadata={"committee_id": str(committee.pk), "teacher_id": str(teacher.pk)},
            request=self.request,
        )

    def perform_update(self, serializer):
        school = self.get_school()
        teacher = serializer.validated_data.get("teacher", serializer.instance.teacher)
        committee = serializer.validated_data.get("committee", serializer.instance.committee)
        if teacher.school_id != school.pk or committee.school_id != school.pk:
            raise ValidationError("المعلم واللجنة يجب أن يتبعا المدرسة النشطة.")
        if not teacher.is_active_teaching or teacher.is_archived:
            raise ValidationError({"teacher": "لا يمكن تكليف معلم غير نشط أو مؤرشف."})
        if committee.branch_id and teacher.branch_id and committee.branch_id != teacher.branch_id:
            raise ValidationError({"teacher": "المعلم يتبع فرعاً مختلفاً عن اللجنة."})
        with transaction.atomic():
            assignment = serializer.save(branch=committee.branch)
            try:
                assignment.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            assignment.save()
        record_event(
            action="assessment.exam_proctor_updated",
            description="تم تحديث تكليف مراقب لجنة.",
            actor=self.request.user, school=school, obj=assignment,
            metadata={"committee_id": str(committee.pk), "teacher_id": str(teacher.pk)},
            request=self.request,
        )

    def perform_destroy(self, instance):
        record_event(
            action="assessment.exam_proctor_unassigned",
            description="تم إلغاء تكليف مراقب لجنة.",
            actor=self.request.user, school=self.get_school(), obj=instance,
            request=self.request,
        )
        super().perform_destroy(instance)


class ExamSeatingViewSet(TenantModelViewSet):
    serializer_class = ExamSeatingSerializer
    read_roles = ACADEMIC_ADMIN_ROLES | {"teacher", "student"}
    write_roles = ACADEMIC_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "student", "committee", "academic_year",
        )
        school = self.get_school()
        if has_school_roles(self.request.user, school, {"student"}) and not is_admin(
            self.request.user, school,
        ):
            student = user_student_profiles(self.request.user, school).first()
            qs = qs.filter(student=student) if student else qs.none()
        elif has_school_roles(self.request.user, school, {"teacher"}) and not is_admin(
            self.request.user, school,
        ):
            teacher = user_teacher_profiles(self.request.user, school).filter(
                is_active_teaching=True,
            ).first()
            if teacher:
                qs = qs.filter(
                    Q(committee__head_supervisor=teacher)
                    | Q(committee__proctor_assignments__teacher=teacher,
                        committee__proctor_assignments__is_archived=False)
                ).distinct()
            else:
                qs = qs.none()
        return qs

    def perform_update(self, serializer):
        school = self.get_school()
        data = serializer.validated_data
        committee = data.get("committee", serializer.instance.committee)
        student = data.get("student", serializer.instance.student)
        academic_year = data.get("academic_year", serializer.instance.academic_year)
        if committee.school_id != school.pk or student.school_id != school.pk or academic_year.school_id != school.pk:
            raise ValidationError("اللجنة والطالب والسنة يجب أن تتبع المدرسة النشطة.")
        if student.academic_year_id and student.academic_year_id != academic_year.pk:
            raise ValidationError({"academic_year": "سنة رقم الجلوس لا تطابق سنة تسجيل الطالب."})
        if committee.branch_id and student.branch_id and committee.branch_id != student.branch_id:
            raise ValidationError({"student": "الطالب يتبع فرعاً مختلفاً عن لجنة الاختبار."})
        with transaction.atomic():
            locked_committee = ExamCommittee.objects.select_for_update().get(pk=committee.pk)
            seating = serializer.save(branch=locked_committee.branch)
            try:
                seating.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            seating.save()
        record_event(
            action="assessment.exam_seating_updated",
            description="تم تعديل توزيع رقم جلوس الطالب.",
            actor=self.request.user, school=school, obj=seating,
            metadata={"committee_id": str(committee.pk), "student_id": str(student.pk)},
            request=self.request,
        )

    def perform_create(self, serializer):
        school = self.get_school()
        committee = serializer.validated_data["committee"]
        student = serializer.validated_data["student"]
        academic_year = serializer.validated_data["academic_year"]
        if student.academic_year_id and student.academic_year_id != academic_year.pk:
            raise ValidationError({"academic_year": "سنة رقم الجلوس لا تطابق سنة تسجيل الطالب."})
        if committee.branch_id and student.branch_id and committee.branch_id != student.branch_id:
            raise ValidationError({"student": "الطالب يتبع فرعاً مختلفاً عن لجنة الاختبار."})
        with transaction.atomic():
            locked_committee = ExamCommittee.objects.select_for_update().get(pk=committee.pk)
            seating = serializer.save(school=school, branch=locked_committee.branch)
            try:
                seating.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            seating.save()
        record_event(
            action="assessment.exam_seating_created",
            description="تم تخصيص رقم جلوس للطالب في لجنة اختبار.",
            actor=self.request.user, school=school, obj=serializer.instance,
            metadata={
                "committee_id": str(committee.pk),
                "student_id": str(student.pk),
                "seating_number": serializer.instance.seating_number,
            },
            request=self.request,
        )


# ---------------------------------------------------------------------------
# Weekly timetable, personal timetable and lesson logs
# ---------------------------------------------------------------------------
class TimetablePlanViewSet(TenantModelViewSet):
    serializer_class = TimetablePlanSerializer
    read_roles = READ_ROLES
    write_roles = ACADEMIC_ADMIN_ROLES
    action_role_map = {
        "list": READ_ROLES, "retrieve": READ_ROLES,
        "create": ACADEMIC_ADMIN_ROLES, "update": ACADEMIC_ADMIN_ROLES,
        "partial_update": ACADEMIC_ADMIN_ROLES, "destroy": ACADEMIC_ADMIN_ROLES,
        "copy": ACADEMIC_ADMIN_ROLES, "submit": ACADEMIC_ADMIN_ROLES,
        "approve": ACADEMIC_ADMIN_ROLES, "publish": ACADEMIC_ADMIN_ROLES,
    }

    def get_queryset(self):
        qs = super().get_queryset().select_related("academic_year", "academic_term", "branch", "bell_schedule")
        branch_id = self.request.query_params.get("branch_id")
        if branch_id:
            try:
                branch_uuid = UUID(str(branch_id))
            except (TypeError, ValueError, AttributeError):
                raise ValidationError({"branch_id": "أرسل معرف فرع صحيحاً بصيغة UUID."})
            branch = Branch.objects.filter(pk=branch_uuid, school=self.get_school(), is_archived=False).first()
            if branch is None:
                raise ValidationError({"branch_id": "الفرع غير موجود أو لا يتبع المدرسة النشطة."})
            qs = qs.filter(branch=branch)
        year_id = self.request.query_params.get("academic_year_id")
        status_filter = self.request.query_params.get("status")
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-academic_year__starts_on", "-version")

    def perform_create(self, serializer):
        school = self.get_school()
        year = serializer.validated_data["academic_year"]
        branch = serializer.validated_data.get("branch")
        if branch is None and year.branch_id:
            branch = year.branch
        if branch and branch.school_id != school.pk:
            raise ValidationError({"branch": "الفرع لا يتبع المدرسة النشطة."})
        version = (TimetablePlan.objects.filter(
            school=school, academic_year=year, branch=branch, is_archived=False,
        ).aggregate(value=Max("version"))["value"] or 0) + 1
        serializer.save(school=school, branch=branch, version=version, status=TimetablePlan.Status.DRAFT, is_current=False)

    def perform_update(self, serializer):
        if serializer.instance.status != TimetablePlan.Status.DRAFT:
            raise ValidationError("لا يمكن تعديل نسخة جدول بعد إرسالها للمراجعة.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != TimetablePlan.Status.DRAFT:
            raise ValidationError("لا يمكن أرشفة نسخة جدول أرسلت للمراجعة أو اعتمدت أو نشرت.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="copy")
    def copy(self, request, pk=None):
        source = self.get_object()
        data = TimetablePlanCopyInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        term = source.academic_term
        if values.get("academic_term_id"):
            term = get_object_or_404(AcademicTerm, pk=values["academic_term_id"], school=self.get_school())
        bell = source.bell_schedule
        if values.get("bell_schedule_id"):
            bell = get_object_or_404(SchoolBellSchedule, pk=values["bell_schedule_id"], school=self.get_school())
        from apps.timetable.services import copy_timetable_plan
        try:
            plan = copy_timetable_plan(
                school=source.school, academic_year=source.academic_year, branch=source.branch,
                source_plan=source, name=values.get("name"), effective_from=values.get("effective_from"),
                academic_term=term, bell_schedule=bell, created_by=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        from apps.timetable.services import submit_timetable_plan
        try:
            plan = submit_timetable_plan(self.get_object(), submitted_by=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
        return Response(self.get_serializer(plan).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        from apps.timetable.services import approve_timetable_plan
        try:
            plan = approve_timetable_plan(self.get_object(), approved_by=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
        return Response(self.get_serializer(plan).data)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        from apps.timetable.services import publish_timetable_plan
        try:
            plan = publish_timetable_plan(self.get_object(), published_by=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
        return Response(self.get_serializer(plan).data)

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
        qs = super().get_queryset().select_related("section", "subject", "teacher__user", "classroom", "academic_year", "timetable_plan")
        plan_id = self.request.query_params.get("timetable_plan_id")
        year = self.request.query_params.get("academic_year_id")
        section = self.request.query_params.get("section_id")
        teacher_id = self.request.query_params.get("teacher_id")
        day = self.request.query_params.get("day_of_week")
        if plan_id:
            qs = qs.filter(timetable_plan_id=plan_id)
            if not is_admin(self.request.user, self.get_school()):
                qs = qs.filter(timetable_plan__status__in=[TimetablePlan.Status.PUBLISHED, TimetablePlan.Status.RETIRED])
        else:
            today = timezone.localdate()
            qs = qs.filter(
                Q(timetable_plan__isnull=True)
                | (
                    Q(timetable_plan__status__in=[TimetablePlan.Status.PUBLISHED, TimetablePlan.Status.RETIRED])
                    & Q(timetable_plan__effective_from__lte=today)
                    & (Q(timetable_plan__effective_to__isnull=True) | Q(timetable_plan__effective_to__gte=today))
                )
            )
            requested_status = self.request.query_params.get("plan_status")
            if requested_status:
                if not is_admin(self.request.user, self.get_school()):
                    raise PermissionDenied("عرض نسخ الجدول غير المنشورة متاح للإدارة الأكاديمية فقط.")
                qs = qs.filter(timetable_plan__status=requested_status)
        if year:
            qs = qs.filter(academic_year_id=year)
        if section:
            qs = qs.filter(section_id=section)
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)
        if day:
            qs = qs.filter(day_of_week=day)
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school()):
            profile = user_teacher_profiles(self.request.user, self.get_school()).filter(is_active_teaching=True).first()
            qs = qs.filter(teacher=profile) if profile else qs.none()
        return qs.order_by("day_of_week", "period_number")

    def perform_create(self, serializer):
        school = self.get_school()
        section = serializer.validated_data["section"]
        plan = serializer.validated_data.get("timetable_plan")
        if plan:
            if plan.school_id != school.pk or plan.status != TimetablePlan.Status.DRAFT:
                raise ValidationError({"timetable_plan": "يمكن إضافة الحصص إلى نسخة مسودة تابعة للمدرسة النشطة فقط."})
            branch = plan.branch
        else:
            branch = section.branch
        serializer.save(school=school, branch=branch)

    def perform_update(self, serializer):
        plan = serializer.instance.timetable_plan
        if plan and plan.status != TimetablePlan.Status.DRAFT:
            raise ValidationError("لا يمكن تعديل حصة في نسخة جدول مرسلة أو معتمدة أو منشورة.")
        serializer.save()

class DailyLessonLogViewSet(TenantModelViewSet):
    serializer_class = DailyLessonLogSerializer
    read_roles = READ_ROLES
    write_roles = TEACHER_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("schedule", "schedule__section", "schedule__subject", "schedule__timetable_plan")
        date_filter = self.request.query_params.get("date")
        section_id = self.request.query_params.get("section_id")
        if date_filter:
            qs = qs.filter(date=date_filter)
        if section_id:
            qs = qs.filter(schedule__section_id=section_id)
        if has_school_roles(self.request.user, self.get_school(), {"teacher"}) and not is_admin(self.request.user, self.get_school()):
            teacher = user_teacher_profiles(self.request.user, self.get_school()).filter(is_active_teaching=True).first()
            qs = qs.filter(schedule__teacher=teacher) if teacher else qs.none()
        return qs

    def perform_create(self, serializer):
        school = self.get_school()
        teacher = user_teacher_profiles(self.request.user, school).filter(is_active_teaching=True).first()
        schedule = serializer.validated_data["schedule"]
        if not is_admin(self.request.user, school):
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك في المدرسة المحددة.")
            if schedule.teacher_id != teacher.pk:
                raise PermissionDenied("لا يمكنك توثيق تنفيذ حصة لمعلم آخر.")
        try:
            serializer.save(school=school, branch=schedule.branch)
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
        record_event(
            action="timetable.lesson_log_created",
            description="تم توثيق تنفيذ الحصة الدراسية.",
            actor=self.request.user, school=school, obj=serializer.instance,
            metadata={"schedule_id": str(schedule.pk), "lesson_date": str(serializer.instance.date)},
            request=self.request,
        )

    def perform_update(self, serializer):
        school = self.get_school()
        schedule = serializer.validated_data.get("schedule", serializer.instance.schedule)
        teacher = user_teacher_profiles(self.request.user, school).filter(
            is_active_teaching=True,
        ).first()
        if not is_admin(self.request.user, school):
            if not teacher or schedule.teacher_id != teacher.pk:
                raise PermissionDenied("لا يمكنك تعديل سجل تنفيذ حصة لمعلم آخر.")
        try:
            serializer.save(branch=schedule.branch)
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
        record_event(
            action="timetable.lesson_log_updated",
            description="تم تعديل سجل تنفيذ حصة دراسية.",
            actor=self.request.user, school=school, obj=serializer.instance,
            metadata={"schedule_id": str(schedule.pk), "lesson_date": str(serializer.instance.date)},
            request=self.request,
        )

class MyWeeklyTimetableAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = school_for(request)
        student = user_student_profiles(request.user, school).first()
        teacher = user_teacher_profiles(request.user, school).filter(is_active_teaching=True).first()
        guardian = user_guardian_profiles(request.user, school).first()
        profile_type = (request.query_params.get("profile_type") or "").strip().lower()
        section_id = request.query_params.get("section_id")
        try:
            on_date = date.fromisoformat(request.query_params["date"]) if request.query_params.get("date") else timezone.localdate()
        except (TypeError, ValueError):
            raise ValidationError({"date": "صيغة التاريخ غير صحيحة؛ استخدم YYYY-MM-DD."})

        available_profiles = []
        if teacher and has_school_roles(request.user, school, {"teacher"}):
            available_profiles.append("teacher")
        if student and has_school_roles(request.user, school, {"student"}):
            available_profiles.append("student")
        if guardian and has_school_roles(request.user, school, {"guardian"}):
            available_profiles.append("guardian")

        if not profile_type:
            if is_admin(request.user, school):
                profile_type = "school"
            elif len(available_profiles) == 1:
                profile_type = available_profiles[0]
            elif len(available_profiles) > 1:
                raise ValidationError({
                    "profile_type": "حسابك يحمل أكثر من دور؛ حدد teacher أو student أو guardian.",
                    "available_profiles": available_profiles,
                })
            else:
                raise PermissionDenied("لا يوجد ملف طالب أو معلم أو ولي أمر مرتبط بدور فعال.")

        from apps.timetable.services import get_effective_class_schedules
        if profile_type == "teacher":
            if not teacher or not has_school_roles(request.user, school, {"teacher"}):
                raise PermissionDenied("لا يوجد ملف معلم فعال مرتبط بحسابك.")
            section_ids = teacher.assignments.filter(school=school, is_archived=False).values_list("section_id", flat=True).distinct()
            schedule_ids = set()
            for assigned_section_id in section_ids:
                schedule_ids.update(get_effective_class_schedules(
                    school=school, on_date=on_date, section_id=assigned_section_id,
                ).filter(teacher=teacher).values_list("pk", flat=True))
            qs = ClassSchedule.objects.filter(pk__in=schedule_ids).select_related("section", "subject", "teacher__user", "classroom")
        elif profile_type == "student":
            if not student or not has_school_roles(request.user, school, {"student"}):
                raise PermissionDenied("لا يوجد ملف طالب فعال مرتبط بحسابك.")
            qs = get_effective_class_schedules(
                school=school, on_date=on_date, branch=student.branch, section_id=student.section_id,
            )
        elif profile_type == "guardian":
            if not guardian or not has_school_roles(request.user, school, {"guardian"}):
                raise PermissionDenied("لا يوجد ملف ولي أمر فعال مرتبط بحسابك.")
            children = guardian.children.filter(school=school, is_archived=False).select_related("branch").order_by("section_id")
            if section_id and not children.filter(section_id=section_id).exists():
                raise PermissionDenied("الشعبة المحددة لا تخص أحد الأبناء المرتبطين بحسابك.")
            schedule_ids = set()
            for child in children:
                if section_id and str(child.section_id) != str(section_id):
                    continue
                schedule_ids.update(get_effective_class_schedules(
                    school=school, on_date=on_date, branch=child.branch, section_id=child.section_id,
                ).values_list("pk", flat=True))
            qs = ClassSchedule.objects.filter(pk__in=schedule_ids).select_related("section", "subject", "teacher__user", "classroom")
        elif profile_type == "school":
            if not is_admin(request.user, school):
                raise PermissionDenied("عرض جدول الشعبة متاح لإدارة المدرسة فقط.")
            if not section_id:
                raise ValidationError({"section_id": "حدد الشعبة عند طلب الجدول المدرسي."})
            section = get_object_or_404(Section.objects.select_related("branch"), pk=section_id, school=school, is_archived=False)
            qs = get_effective_class_schedules(
                school=school, on_date=on_date, branch=section.branch, section_id=section.pk,
            )
        else:
            raise ValidationError({"profile_type": "القيمة المدعومة teacher أو student أو guardian أو school."})

        return Response([{
            "id": str(item.pk),
            "day_of_week": item.day_of_week,
            "period_number": item.period_number,
            "start_time": item.start_time,
            "end_time": item.end_time,
            "subject": item.subject.name,
            "section": item.section.name,
            "section_id": str(item.section_id),
            "teacher": item.teacher.user.get_full_name(),
            "classroom": item.classroom.name if item.classroom_id else None,
        } for item in qs.order_by("day_of_week", "period_number")])

# ---------------------------------------------------------------------------
# Accounting: chart, fiscal periods, journals and double-entry vouchers
# ---------------------------------------------------------------------------
class FiscalYearViewSet(TenantModelViewSet):
    serializer_class = FiscalYearSerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES


class FiscalPeriodViewSet(TenantModelViewSet):
    serializer_class = FiscalPeriodSerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("fiscal_year")
        year_id = self.request.query_params.get("fiscal_year_id")
        return qs.filter(fiscal_year_id=year_id) if year_id else qs


class AccountViewSet(TenantModelViewSet):
    serializer_class = AccountSerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES

    def get_queryset(self):
        qs = super().get_queryset().select_related("parent").order_by("code")
        account_type = self.request.query_params.get("account_type")
        if account_type:
            qs = qs.filter(account_type=account_type)
        return qs


class CostCenterViewSet(TenantModelViewSet):
    serializer_class = CostCenterSerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES


class ExpenseCategoryViewSet(TenantModelViewSet):
    serializer_class = ExpenseCategorySerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES


class JournalEntryViewSet(TenantModelViewSet):
    serializer_class = JournalEntrySerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES
    action_role_map = {
        "list": FINANCE_ADMIN_ROLES,
        "retrieve": FINANCE_ADMIN_ROLES,
        "create": FINANCE_ADMIN_ROLES,
        "post": FINANCE_ADMIN_ROLES,
        "reverse": FINANCE_ADMIN_ROLES,
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
        period = get_object_or_404(
            FiscalPeriod, pk=data["fiscal_period_id"],
            school=school, is_archived=False,
        )
        if (
            period.is_closed or period.fiscal_year.is_closed
            or not (period.start_date <= data["date"] <= period.end_date)
        ):
            raise ValidationError("الفترة المالية مغلقة أو تاريخ القيد خارج حدودها.")
        entry_number = (
            request.data.get("entry_number")
            or f"MAN-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        ).strip()
        if not entry_number or len(entry_number) > 50:
            raise ValidationError({"entry_number": "رقم القيد مطلوب وبحد أقصى 50 حرفاً."})
        try:
            with transaction.atomic():
                if JournalEntry.objects.filter(
                    school=school, entry_number=entry_number, is_archived=False,
                ).exists():
                    raise ValidationError({"entry_number": "رقم القيد مستخدم مسبقاً في المدرسة."})
                entry = JournalEntry.objects.create(
                    school=school, fiscal_period=period, entry_number=entry_number,
                    date=data["date"], description=data["description"],
                    status=JournalEntry.Status.DRAFT, source_module="manual_api",
                    source_reference="",
                )
                self._replace_lines(entry, data["lines"], school)
        except IntegrityError as exc:
            raise ValidationError({"entry_number": "رقم القيد مستخدم مسبقاً في المدرسة."}) from exc
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)

    def _replace_lines(self, entry, lines, school):
        entry.lines.all().delete()
        for item in lines:
            account = get_object_or_404(
                Account, pk=item["account_id"], school=school, is_leaf=True,
                is_archived=False,
            )
            cost_center = None
            if item.get("cost_center_id"):
                cost_center = get_object_or_404(
                    CostCenter, pk=item["cost_center_id"],
                    school=school, is_archived=False,
                )
            JournalEntryLine.objects.create(
                school=school, journal_entry=entry, account=account,
                cost_center=cost_center,
                debit=Decimal(str(item.get("debit", "0"))),
                credit=Decimal(str(item.get("credit", "0"))),
                description=item.get("description", ""),
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = JournalEntryUpdateSerializer(
            data=request.data, partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        school = self.get_school()
        with transaction.atomic():
            entry = get_object_or_404(
                JournalEntry.objects.select_for_update(),
                pk=kwargs.get("pk"), school=school, is_archived=False,
            )
            if entry.status != JournalEntry.Status.DRAFT:
                raise ValidationError("لا يمكن تعديل قيد مرحّل؛ استخدم قيداً عكسياً.")

            new_date = data.get("date", entry.date)
            period_id = data.get("fiscal_period_id", entry.fiscal_period_id)
            period = get_object_or_404(
                FiscalPeriod, pk=period_id, school=school, is_archived=False,
            )
            if (
                period.is_closed or period.fiscal_year.is_closed
                or not (period.start_date <= new_date <= period.end_date)
            ):
                raise ValidationError("الفترة المالية مغلقة أو تاريخ القيد خارج حدودها.")

            if "lines" in data:
                self._replace_lines(entry, data["lines"], school)
            entry.date = new_date
            entry.fiscal_period = period
            if "description" in data:
                entry.description = data["description"]
            entry.save(update_fields=[
                "date", "fiscal_period", "description", "updated_at",
            ])
        return Response(self.get_serializer(entry).data)

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
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES

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
    read_roles = INVENTORY_ROLES | FINANCE_ADMIN_ROLES
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
    read_roles = INVENTORY_ROLES | FINANCE_ADMIN_ROLES
    write_roles = INVENTORY_ROLES
    action_role_map = {
        "list": INVENTORY_ROLES | FINANCE_ADMIN_ROLES,
        "retrieve": INVENTORY_ROLES | FINANCE_ADMIN_ROLES,
        "approve": FINANCE_ADMIN_ROLES,
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
    read_roles = INVENTORY_ROLES | FINANCE_ADMIN_ROLES
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
    read_roles = INVENTORY_ROLES | FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES
    action_role_map = {
        "list": INVENTORY_ROLES | FINANCE_ADMIN_ROLES,
        "retrieve": INVENTORY_ROLES | FINANCE_ADMIN_ROLES,
        "approve": FINANCE_ADMIN_ROLES,
        "post": FINANCE_ADMIN_ROLES,
        "record_payment": FINANCE_ADMIN_ROLES,
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
        except Exception as exc:
            raise ValidationError({"amount": "المبلغ غير صحيح."}) from exc

        idempotency_key = (request.data.get("idempotency_key") or "").strip()
        if len(idempotency_key) < 8 or len(idempotency_key) > 120:
            raise ValidationError({
                "idempotency_key": "أرسل مفتاحاً فريداً من 8 إلى 120 حرفاً لإعادة المحاولة بأمان.",
            })

        payment_method = request.data.get("payment_method", PaymentVoucher.PaymentMethod.BANK_TRANSFER)
        if payment_method not in PaymentVoucher.PaymentMethod.values:
            raise ValidationError({"payment_method": "طريقة الدفع غير مدعومة."})

        payment_account = get_object_or_404(
            Account, pk=request.data.get("payment_account_id"),
            school=self.get_school(), is_leaf=True,
            account_type=Account.AccountType.ASSET,
        )
        from apps.accounting.services.auto_posting import (
            _get_account_or_seed, _get_active_fiscal_period,
        )
        school = self.get_school()
        key_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        source_reference = f"{pk}:{key_digest}"

        with transaction.atomic():
            invoice = get_object_or_404(
                VendorInvoice.objects.select_for_update(),
                pk=pk, school=school, is_archived=False,
            )
            if not invoice.journal_entry_id:
                raise ValidationError("يجب ترحيل فاتورة المورد محاسبياً قبل تسجيل السداد.")

            existing_entry = JournalEntry.objects.filter(
                school=school,
                source_module="vendor_invoice_payment",
                source_reference=source_reference,
                is_archived=False,
            ).first()
            if existing_entry:
                existing_total = sum(
                    (line.debit for line in existing_entry.lines.all()),
                    Decimal("0.00"),
                )
                if existing_total != amount:
                    raise ValidationError({
                        "idempotency_key": "استُخدم هذا المفتاح سابقاً بمبلغ مختلف.",
                    })
                existing_voucher = PaymentVoucher.objects.filter(
                    school=school, journal_entry=existing_entry,
                ).first()
                if existing_voucher is None:
                    raise ValidationError(
                        "تم العثور على قيد سداد سابق دون سند مرتبط؛ يلزم مراجعة المحاسبة.",
                    )
                return Response({
                    "invoice": self.get_serializer(invoice).data,
                    "payment_voucher": PaymentVoucherSerializer(existing_voucher).data,
                    "journal_entry": existing_entry.entry_number,
                    "idempotent_replay": True,
                })

            if invoice.status not in {
                VendorInvoice.Status.APPROVED,
                VendorInvoice.Status.PARTIAL,
            }:
                raise ValidationError("فاتورة المورد ليست في حالة تسمح بالسداد.")
            if amount <= 0 or amount > invoice.remaining_amount:
                raise ValidationError({
                    "amount": f"المبلغ يجب أن يكون أكبر من صفر ولا يتجاوز المتبقي {invoice.remaining_amount}.",
                })

            period = _get_active_fiscal_period(school, timezone.localdate())
            ap = _get_account_or_seed(school, "2101", "ذمم الموردين")
            entry_number = f"JV-VENDOR-PAY-{invoice.pk.hex[:8]}-{key_digest[:12].upper()}"
            entry = JournalEntry.objects.create(
                school=school,
                fiscal_period=period,
                entry_number=entry_number,
                date=timezone.localdate(),
                description=f"سداد فاتورة المورد #{invoice.invoice_number}",
                status=JournalEntry.Status.DRAFT,
                source_module="vendor_invoice_payment",
                source_reference=source_reference,
            )
            JournalEntryLine.objects.create(
                school=school, journal_entry=entry, account=ap,
                debit=amount, credit=Decimal("0.00"),
                description="تسوية ذمم المورد",
            )
            JournalEntryLine.objects.create(
                school=school, journal_entry=entry, account=payment_account,
                debit=Decimal("0.00"), credit=amount,
                description="السداد من الصندوق/البنك",
            )
            entry.post(user=request.user)

            voucher = PaymentVoucher.objects.create(
                school=school,
                voucher_number=f"PV-VINV-{invoice.pk.hex[:8].upper()}-{key_digest[:12].upper()}",
                date=timezone.localdate(),
                paid_to=invoice.supplier.name,
                amount=amount,
                payment_method=payment_method,
                credit_account=payment_account,
                debit_account=ap,
                description=f"سداد فاتورة المورد #{invoice.invoice_number}",
                reference_number=request.data.get("reference_number", "")[:100],
                status=PaymentVoucher.Status.POSTED,
                journal_entry=entry,
            )
            invoice.paid_amount += amount
            invoice.status = (
                VendorInvoice.Status.PAID
                if invoice.paid_amount == invoice.total_amount
                else VendorInvoice.Status.PARTIAL
            )
            invoice.save(update_fields=["paid_amount", "status", "updated_at"])

        return Response({
            "invoice": self.get_serializer(invoice).data,
            "payment_voucher": PaymentVoucherSerializer(voucher).data,
            "journal_entry": entry.entry_number,
            "idempotent_replay": False,
        }, status=status.HTTP_201_CREATED)


class AssetCategoryViewSet(TenantModelViewSet):
    serializer_class = AssetCategorySerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES


class FixedAssetViewSet(TenantModelViewSet):
    serializer_class = FixedAssetSerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES

    def get_queryset(self):
        return super().get_queryset().select_related("category", "custodian").order_by("name")


class AssetDepreciationViewSet(TenantModelViewSet):
    serializer_class = AssetDepreciationSerializer
    read_roles = FINANCE_ADMIN_ROLES
    write_roles = FINANCE_ADMIN_ROLES

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
        self.get_participant(conv)
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
            allowed = allowed or bool(
                student and submission.student_id == student.pk
            )
        if has_school_roles(request.user, school, {"guardian"}):
            guardian = user_guardian_profiles(request.user, school).first()
            allowed = allowed or bool(
                guardian
                and guardian.children.filter(pk=submission.student_id).exists()
            )
        if has_school_roles(request.user, school, {"teacher"}):
            teacher = user_teacher_profiles(request.user, school).filter(is_active_teaching=True).first()
            allowed = allowed or bool(
                teacher and submission.homework.teacher_id == teacher.pk
            )
        if not allowed or not submission.attachment:
            raise Http404
        filename = os.path.basename(submission.attachment.name)
        return FileResponse(submission.attachment.open("rb"), as_attachment=True, filename=filename)
