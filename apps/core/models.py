"""Shared abstract model primitives. Business rules stay in owning apps."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UUIDTimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField("تاريخ الإنشاء", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class ArchivableModel(models.Model):
    is_archived = models.BooleanField("مؤرشف", default=False, db_index=True)
    archived_at = models.DateTimeField("تاريخ الأرشفة", null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="أرشفه", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="%(app_label)s_%(class)s_archived",
    )
    archive_reason = models.CharField("سبب الأرشفة", max_length=500, blank=True)

    class Meta:
        abstract = True

    def archive(self, *, actor=None, reason: str = "") -> None:
        self.is_archived = True
        self.archived_at = timezone.now()
        self.archived_by = actor
        self.archive_reason = reason[:500]
        self.save(update_fields=["is_archived", "archived_at", "archived_by", "archive_reason", "updated_at"])

    def restore(self) -> None:
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = ""
        self.save(update_fields=["is_archived", "archived_at", "archived_by", "archive_reason", "updated_at"])


class TenantQuerySet(models.QuerySet):
    def for_school(self, school):
        if school is None:
            raise ValueError("يجب تحديد المدرسة صراحة عند الاستعلام عن سجلاتها.")
        return self.filter(school=school)

    def active(self):
        return self.filter(is_archived=False)


class TenantOwnedModel(UUIDTimestampedModel, ArchivableModel):
    """Base for operational rows that belong directly to one school."""
    school = models.ForeignKey(
        "tenants.School", verbose_name="المدرسة", on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_records", db_index=True,
    )
    branch = models.ForeignKey(
        "tenants.Branch", verbose_name="الفرع", null=True, blank=True,
        on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_records",
    )

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["school", "created_at"])]

    def clean(self):
        super().clean()
        if self.school_id is None:
            raise ValidationError({"school": "كل سجل تشغيلي يجب أن يرتبط بمدرسة محددة."})
        if self.branch_id and self.school_id:
            branch_school_id = self.branch.school_id if "branch" in self._state.fields_cache else None
            if branch_school_id is None:
                branch_school_id = self.branch.__class__.objects.filter(pk=self.branch_id).values_list("school_id", flat=True).first()
            if branch_school_id != self.school_id:
                raise ValidationError({"branch": "الفرع المحدد لا يتبع المدرسة نفسها."})

    def save(self, *args, **kwargs):
        # Enforce tenant/branch validation for ORM callers as well as ModelForms.
        self.full_clean()
        return super().save(*args, **kwargs)
