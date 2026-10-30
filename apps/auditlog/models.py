"""Append-only audit trail for sensitive and administrative actions."""
from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimestampedModel


class AuditEventQuerySet(models.QuerySet):
    """Prevent application code from bypassing append-only event semantics."""

    def update(self, **kwargs):
        raise ValueError("سجل التدقيق غير قابل للتعديل الجماعي.")

    def delete(self):
        raise ValueError("سجل التدقيق غير قابل للحذف الجماعي.")


class AuditEvent(UUIDTimestampedModel):
    class Severity(models.TextChoices):
        INFO = "info", "معلومات"
        WARNING = "warning", "تحذير"
        CRITICAL = "critical", "حرج"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="منفذ العملية", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField("الإجراء", max_length=80, db_index=True)
    object_type = models.CharField("نوع السجل", max_length=120, blank=True, db_index=True)
    object_id = models.CharField("معرف السجل", max_length=64, blank=True, db_index=True)
    description = models.CharField("الوصف", max_length=500)
    severity = models.CharField("الخطورة", max_length=10, choices=Severity.choices, default=Severity.INFO)
    metadata = models.JSONField("تفاصيل إضافية", default=dict, blank=True)
    request_id = models.CharField("معرف الطلب", max_length=80, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField("عنوان IP", null=True, blank=True)
    user_agent = models.CharField("المتصفح / الجهاز", max_length=500, blank=True)
    occurred_at = models.DateTimeField("وقت العملية", db_index=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        verbose_name = "حدث تدقيق"
        verbose_name_plural = "سجل التدقيق"
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["school", "occurred_at"]), models.Index(fields=["actor", "occurred_at"])]

    def __str__(self):
        return f"{self.action}: {self.description[:70]}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("سجلات التدقيق غير قابلة للتعديل؛ أنشئ حدثاً تصحيحياً جديداً.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("سجلات التدقيق غير قابلة للحذف من التطبيق.")
