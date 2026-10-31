"""
Centralized API security, school context resolution, and role-based permissions.
Enforces strict tenant isolation, active non-expired membership checks, and granular role authorization.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import SchoolMembership
from apps.accounts.services import is_platform_operator, has_school_permission
from apps.tenants.models import School


def resolve_active_school(request) -> School | None:
    """
    تحديد المدرسة النشطة للمستخدم مع التحقق الصارم من سريان العضوية وعدم انتهائها.
    """
    if getattr(request, "school_context_error", None):
        return None
    if getattr(request, "school", None):
        return request.school

    if not request.user or not request.user.is_authenticated:
        return None

    school_id = request.headers.get("X-School-ID") or request.query_params.get("school_id")
    school_code = request.headers.get("X-School-Code") or request.query_params.get("school_code")

    # Platform operators can access any active school
    if is_platform_operator(request.user):
        if school_id:
            return School.objects.filter(pk=school_id, status=School.Status.ACTIVE).first()
        if school_code:
            return School.objects.filter(code=school_code.upper(), status=School.Status.ACTIVE).first()
        active_schools = School.objects.filter(status=School.Status.ACTIVE)
        return active_schools.first() if active_schools.count() == 1 else None

    # Regular users must have an ACTIVE, NON-EXPIRED membership
    now = timezone.now()
    active_memberships = request.user.school_memberships.filter(
        status=SchoolMembership.Status.ACTIVE,
        school__status=School.Status.ACTIVE,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).select_related("school")

    if school_id:
        m = active_memberships.filter(school_id=school_id).first()
        return m.school if m else None

    if school_code:
        m = active_memberships.filter(school__code=school_code.upper()).first()
        return m.school if m else None

    # Never silently choose the first school for a multi-school account.
    default_membership = active_memberships.filter(is_default=True).first()
    if default_membership:
        return default_membership.school
    if active_memberships.count() == 1:
        only_membership = active_memberships.first()
        return only_membership.school if only_membership else None
    return None


def require_school_context(request) -> School:
    """إرجاع المدرسة النشطة أو رمي خطأ PermissionDenied فوري عند انعدام العضوية أو انتهائها."""
    school = resolve_active_school(request)
    if not school:
        raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك عضوية نشطة سارية المفعول في هذه المدرسة.")
    return school


def has_school_roles(user, school: School, allowed_roles: set[str]) -> bool:
    """التحقق من حيازة المستخدم لأحد الأدوار المدرسية المحددة."""
    if not user or not user.is_authenticated or not school:
        return False
    if is_platform_operator(user):
        return True

    now = timezone.now()
    membership = user.school_memberships.filter(
        school=school,
        status=SchoolMembership.Status.ACTIVE,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).first()

    if not membership:
        return False

    user_roles = membership.get_role_codes()
    normalized_allowed = {r.replace("_", "-") for r in allowed_roles} | {r.replace("-", "_") for r in allowed_roles}
    return bool(user_roles & normalized_allowed)


def require_school_role_or_permission(request, school: School, allowed_roles: set[str], permission_codename: str | None = None):
    """
    فرض امتلاك المستخدم لدور وظيفي مصرح به أو صلاحية نظام محددة لتنفيذ العمليات الحساسة.
    """
    if is_platform_operator(request.user):
        return

    # Check role
    if allowed_roles and has_school_roles(request.user, school, allowed_roles):
        return

    # Check permission
    if permission_codename and has_school_permission(user=request.user, school=school, permission=permission_codename):
        return

    raise PermissionDenied("ليس لديك الصلاحية أو الدور الوظيفي المطلوب لتنفيذ هذا الإجراء في المدرسة.")


FINANCIAL_ROLES = {"school-director", "school_director", "accountant", "school-accountant", "school_accountant", "financial-manager", "financial_manager"}
HR_ROLES = {"school-director", "school_director", "hr", "hr-specialist", "hr_specialist", "principal", "school-principal"}
STUDENT_AFFAIRS_ROLES = {"school-director", "school_director", "student-affairs", "student_affairs", "registrar", "academic-coordinator", "academic_coordinator"}
