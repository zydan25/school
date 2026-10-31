"""Centralized permission and membership services."""
import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import MembershipRole, PlatformAccess, SchoolMembership


def active_membership(*, user, school):
    return SchoolMembership.objects.filter(
        user=user, school=school, status=SchoolMembership.Status.ACTIVE,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()


def has_platform_permission(*, user, permission: str) -> bool:
    """Resolve central permissions separately from school-scoped roles."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if "." not in permission:
        return False
    app_label, codename = permission.split(".", 1)
    accesses = PlatformAccess.objects.filter(user=user, is_active=True)
    if accesses.filter(role__in=[PlatformAccess.Role.OWNER, PlatformAccess.Role.OPERATIONS]).exists():
        return True
    return accesses.filter(
        permissions__content_type__app_label=app_label,
        permissions__codename=codename,
    ).exists()


def is_platform_operator(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return PlatformAccess.objects.filter(
        user=user, is_active=True,
        role__in=[PlatformAccess.Role.OWNER, PlatformAccess.Role.OPERATIONS],
    ).exists()


SCHOOL_PERMISSION_APP_LABELS = {
    "academics", "students", "staff", "timetable", "attendance",
    "assignments", "assessments", "student_fees", "accounting",
    "payroll", "assets", "inventory", "school_services", "reports",
    "notifications", "copilot",
}


def is_school_permission_allowed(permission) -> bool:
    """School roles cannot grant Django, account, tenant or platform privileges."""
    content_type = getattr(permission, "content_type", None)
    if content_type is None or content_type.app_label not in SCHOOL_PERMISSION_APP_LABELS:
        return False
    codename = getattr(permission, "codename", "")
    return codename.startswith(("view_", "add_", "change_", "delete_"))


def school_assignable_permissions():
    from django.contrib.auth.models import Permission
    from django.db.models import Q

    actions = Q()
    for prefix in ("view_", "add_", "change_", "delete_"):
        actions |= Q(codename__startswith=prefix)
    return Permission.objects.filter(
        content_type__app_label__in=SCHOOL_PERMISSION_APP_LABELS,
    ).filter(actions).select_related("content_type").distinct()


def has_school_permission(*, user, school, permission: str) -> bool:
    """Check `app_label.codename`; a hidden UI control is never an authorization rule."""
    if not user or not user.is_authenticated or school is None:
        return False
    if is_platform_operator(user):
        return True
    membership = active_membership(user=user, school=school)
    if membership is None or "." not in permission:
        return False
    app_label, codename = permission.split(".", 1)
    if app_label not in SCHOOL_PERMISSION_APP_LABELS or not codename.startswith(
        ("view_", "add_", "change_", "delete_")
    ):
        return False
    today = timezone.localdate()
    assignments = MembershipRole.objects.filter(
        membership=membership,
        role__is_active=True,
        role__is_archived=False,
        valid_from__lte=today,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
    return assignments.filter(
        role__permissions__content_type__app_label=app_label,
        role__permissions__codename=codename,
    ).exists()


def require_school_permission(*, user, school, permission: str) -> None:
    if not has_school_permission(user=user, school=school, permission=permission):
        raise PermissionDenied("لا تملك الصلاحية المطلوبة في هذه المدرسة.")


def switch_active_school(*, user, school):
    membership = active_membership(user=user, school=school)
    if membership is None and not is_platform_operator(user):
        raise PermissionDenied("لا تملك عضوية نشطة في المدرسة المطلوبة.")
    return membership


@transaction.atomic
def issue_school_invitation(*, school, invited_by, email, expires_at, roles=None, phone="", message=""):
    from apps.accounts.models import SchoolInvitation

    selected_roles = list(roles or [])
    if any(role.school_id != school.pk for role in selected_roles):
        raise ValidationError("لا يجوز إرفاق دور تابع لمدرسة أخرى بالدعوة.")
    invitation, raw_token = SchoolInvitation.create_invitation(
        school=school, invited_by=invited_by, email=email.strip().lower(),
        phone=phone, expires_at=expires_at, message=message,
    )
    if selected_roles:
        invitation.roles.set(selected_roles)
    return invitation, raw_token


def accept_school_invitation(*, raw_token, user):
    """Accept once; an expired state is committed before the error is returned."""
    from apps.accounts.models import SchoolInvitation
    from apps.auditlog.services import record_event

    expired = False
    membership = None
    with transaction.atomic():
        digest = hashlib.sha256(raw_token.encode()).hexdigest()
        invitation = (
            SchoolInvitation.objects.select_for_update()
            .filter(token_digest=digest).select_related("school").first()
        )
        if invitation is None or not invitation.matches_token(raw_token):
            raise ValidationError("رمز الدعوة غير صحيح أو غير موجود.")
        if invitation.status != SchoolInvitation.Status.PENDING:
            raise ValidationError("هذه الدعوة لم تعد صالحة للقبول.")
        if invitation.expires_at <= timezone.now():
            invitation.status = SchoolInvitation.Status.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            expired = True
        elif invitation.school.status != "active" or invitation.school.is_archived:
            raise ValidationError("لا يمكن قبول دعوة لمدرسة غير نشطة.")
        elif invitation.phone:
            if user.phone != invitation.phone:
                raise ValidationError("رقم الهاتف لا يطابق رقم الهاتف المحدد في الدعوة.")
            if user.phone_verified_at is None:
                raise ValidationError("يجب توثيق رقم الهاتف قبل قبول الدعوة.")
            if invitation.email and user.email.strip().lower() != invitation.email.strip().lower():
                raise ValidationError("البريد الإلكتروني لا يطابق الدعوة.")
        elif invitation.email:
            if user.email.strip().lower() != invitation.email.strip().lower():
                raise ValidationError("يجب تسجيل الدخول بالبريد الإلكتروني الذي استلم الدعوة.")
            if user.email_verified_at is None:
                raise ValidationError("يجب توثيق البريد الإلكتروني قبل قبول الدعوة.")
        else:
            membership, _ = SchoolMembership.objects.get_or_create(
                school=invitation.school, user=user,
                defaults={
                    "status": SchoolMembership.Status.ACTIVE,
                    "joined_at": timezone.now(),
                    "invited_by": invitation.invited_by,
                },
            )
            membership.status = SchoolMembership.Status.ACTIVE
            membership.joined_at = membership.joined_at or timezone.now()
            membership.save(update_fields=["status", "joined_at", "updated_at"])
            for role in invitation.roles.select_related("school"):
                if role.school_id != invitation.school_id:
                    raise ValidationError("تحتوي الدعوة على دور تابع لمدرسة أخرى.")
                MembershipRole.objects.get_or_create(
                    membership=membership, role=role,
                    defaults={"assigned_by": invitation.invited_by, "valid_from": timezone.localdate()},
                )
            invitation.status = SchoolInvitation.Status.ACCEPTED
            invitation.accepted_by = user
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["status", "accepted_by", "accepted_at", "updated_at"])
            record_event(
                action="school_invitation.accepted",
                description="قبول دعوة الانضمام إلى المدرسة",
                actor=user, school=invitation.school, obj=invitation,
                metadata={"membership_id": str(membership.pk)},
            )
    if expired:
        raise ValidationError("انتهت صلاحية الدعوة؛ اطلب إرسال دعوة جديدة.")
    return membership
