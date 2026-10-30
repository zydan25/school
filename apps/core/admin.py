"""Reusable admin behaviors shared by the central and tenant admin sites."""
from apps.auditlog.services import record_event


class AuditedAdminMixin:
    """Record who created or changed each managed record from the Django admin."""
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        school = getattr(obj, "school", None)
        if school is None and getattr(obj, "membership_id", None):
            school = obj.membership.school
        label = obj._meta.verbose_name
        action = f"admin.{obj._meta.app_label}.{obj._meta.model_name}.{'updated' if change else 'created'}"
        record_event(
            action=action,
            description=f"{'تحديث' if change else 'إنشاء'} سجل: {label}",
            actor=request.user,
            school=school,
            obj=obj,
            metadata={"changed_fields": list(getattr(form, "changed_data", []))},
            request=request,
        )
