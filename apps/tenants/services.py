"""Tenant provisioning and authenticated school-context resolution."""
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole
from apps.accounts.services import is_platform_operator
from apps.auditlog.services import record_event
from apps.tenants.models import Branch, School, SchoolSettings


def resolve_school_for_user(*, user, school_code: str) -> School:
    school = School.objects.filter(code=school_code.strip().upper(), status=School.Status.ACTIVE).first()
    if school is None:
        raise PermissionDenied("المدرسة غير متاحة.")
    if is_platform_operator(user):
        return school
    if not SchoolMembership.objects.filter(user=user, school=school, status=SchoolMembership.Status.ACTIVE).exists():
        raise PermissionDenied("لا تملك عضوية نشطة في هذه المدرسة.")
    return school


def require_school(request) -> School:
    if getattr(request, "school_context_error", None):
        raise PermissionDenied(request.school_context_error)
    school = getattr(request, "school", None)
    if school is None:
        raise PermissionDenied("اختر مدرسة نشطة قبل تنفيذ العملية.")
    return school


def _create_default_roles(school: School, membership: SchoolMembership):
    """Create least-privilege starter roles; schools may subsequently customize them."""
    module_models = {
        "tenants": None,
        "academics": None,
        "accounts": {"schoolmembership", "schoolrole", "membershiprole"},
        "notifications": {"notification", "notificationtemplate", "notificationpreference"},
    }
    all_permissions = Permission.objects.none()
    for app_label, model_names in module_models.items():
        query = Permission.objects.filter(content_type__app_label=app_label)
        if model_names is not None:
            query = query.filter(content_type__model__in=model_names)
        query = query.filter(Q(codename__startswith="view_") | Q(codename__startswith="add_") | Q(codename__startswith="change_"))
        all_permissions = all_permissions | query

    director, _ = SchoolRole.objects.get_or_create(
        school=school, code="school-director",
        defaults={"name": "مدير المدرسة", "description": "إدارة شؤون المدرسة والهيكل الأكاديمي والمستخدمين ضمن هذه المدرسة فقط.", "is_system": True},
    )
    director.permissions.set(all_permissions.distinct())
    MembershipRole.objects.get_or_create(
        membership=membership, role=director,
        defaults={"valid_from": timezone.localdate()},
    )

    academic_permissions = Permission.objects.filter(content_type__app_label="academics").filter(
        Q(codename__startswith="view_") | Q(codename__startswith="add_") | Q(codename__startswith="change_")
    )
    academic, _ = SchoolRole.objects.get_or_create(
        school=school, code="academic-coordinator",
        defaults={"name": "منسق أكاديمي", "description": "إدارة السنوات والمراحل والصفوف والشعب والمواد والفترات.", "is_system": True},
    )
    academic.permissions.set(academic_permissions.distinct())

    auditor_permissions = Permission.objects.filter(content_type__app_label__in=["academics", "tenants"]).filter(codename__startswith="view_")
    auditor, _ = SchoolRole.objects.get_or_create(
        school=school, code="school-auditor",
        defaults={"name": "مراجع مدرسي", "description": "اطلاع فقط على إعدادات المدرسة والهيكل الأكاديمي.", "is_system": True},
    )
    auditor.permissions.set(auditor_permissions.distinct())


def provision_school(school: School, *, actor=None):
    """Create branch, settings, owner membership and default roles in one transaction."""
    with transaction.atomic():
        if not school.pk:
            raise ValidationError("يجب حفظ المدرسة قبل تهيئتها.")
        Branch.objects.get_or_create(
            school=school, code="MAIN",
            defaults={"name": "الفرع الرئيسي", "is_main": True, "status": "active"},
        )
        SchoolSettings.objects.get_or_create(school=school)
        membership, _ = SchoolMembership.objects.get_or_create(
            school=school,
            user=school.owner,
            defaults={"status": SchoolMembership.Status.ACTIVE, "is_default": True, "joined_at": timezone.now(), "invited_by": actor},
        )
        changed_fields = []
        if membership.status != SchoolMembership.Status.ACTIVE:
            membership.status = SchoolMembership.Status.ACTIVE
            membership.joined_at = membership.joined_at or timezone.now()
            changed_fields.extend(["status", "joined_at"])
        has_other_default = SchoolMembership.objects.filter(
            user=school.owner, status=SchoolMembership.Status.ACTIVE, is_default=True,
        ).exclude(pk=membership.pk).exists()
        if not has_other_default and not membership.is_default:
            membership.is_default = True
            changed_fields.append("is_default")
        if changed_fields:
            membership.save(update_fields=[*changed_fields, "updated_at"])
        _create_default_roles(school, membership)
        record_event(
            action="school.provisioned", description="تهيئة المدرسة وإنشاء الهيكل الأساسي والصلاحيات الافتراضية",
            actor=actor, school=school, obj=school,
        )
        return membership


@transaction.atomic
def activate_school(school: School, *, actor=None):
    if school.owner_id is None:
        raise ValidationError({"owner": "يجب تعيين مدير / مالك للمدرسة قبل تفعيلها."})
    school.status = School.Status.ACTIVE
    school.activated_at = school.activated_at or timezone.now()
    school.is_archived = False
    school.archived_at = None
    school.archived_by = None
    school.archive_reason = ""
    school.save(update_fields=[
        "status", "activated_at", "is_archived", "archived_at",
        "archived_by", "archive_reason", "updated_at",
    ])
    return provision_school(school, actor=actor)
