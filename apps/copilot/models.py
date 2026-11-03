"""AI Copilot (Teacher & Student) models and grounding persistence."""
from __future__ import annotations

import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import UUIDTimestampedModel, TenantOwnedModel


def curriculum_document_upload_path(instance: CurriculumDocument, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"schools/{instance.school_id}/curriculum/{instance.subject_id}/{instance.id}{ext}"


class CurriculumDocument(TenantOwnedModel):
    """مستندات المناهج الدراسية المرفوعة لدعم استرجاع RAG وتدريس الذكاء الاصطناعي."""
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="curriculum_documents",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي المستهدف",
        on_delete=models.PROTECT,
        related_name="curriculum_documents",
        null=True,
        blank=True,
    )
    title = models.CharField("عنوان المستند المنهجي", max_length=255)
    description = models.TextField("وصف ومحاور الوحدة الدراسية", blank=True)
    file = models.FileField("ملف المنهج (PDF / نصي)", upload_to=curriculum_document_upload_path)
    extracted_text = models.TextField("النص المستخرج للبحث الدلالي", blank=True)
    uploaded_by = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم الرافع",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_curricula",
    )
    is_indexed = models.BooleanField("تمت الفهرسة وتوليد التضمين", default=False)

    class Meta:
        verbose_name = "مستند منهجي"
        verbose_name_plural = "وثائق المناهج الدراسية"
        indexes = [
            models.Index(fields=["school", "subject", "grade_level"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} - {self.subject.name}"

    def clean(self):
        super().clean()
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة الدراسية لا تتبع نفس المدرسة."})


class AIChatSession(TenantOwnedModel):
    """جلسات المحادثة المستمرة للـ Co-Pilot لحفظ الذاكرة وسياق الحوار."""
    class RoleScope(models.TextChoices):
        TEACHER = "teacher", "مساعد المعلم (Teacher Co-Pilot)"
        STUDENT = "student", "مساعد الطالب (Student Co-Pilot)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المستخدم صاحب الجلسة",
        on_delete=models.CASCADE,
        related_name="ai_chat_sessions",
    )
    role_scope = models.CharField("نوع المساعد", max_length=20, choices=RoleScope.choices)
    title = models.CharField("عنوان الجلسة", max_length=255, default="محادثة جديدة")
    model_name = models.CharField("نموذج الذكاء الاصطناعي", max_length=100, default="gemini-2.5-flash")
    is_active = models.BooleanField("جلسة نشطة", default=True)

    class Meta:
        verbose_name = "جلسة ذكاء اصطناعي"
        verbose_name_plural = "جلسات الذكاء الاصطناعي"
        indexes = [
            models.Index(fields=["school", "user", "role_scope"]),
        ]

    def __str__(self) -> str:
        return f"[{self.get_role_scope_display()}] {self.title} ({self.user.phone})"


class AIChatMessage(TenantOwnedModel):
    """رسائل المحادثة داخل جلسة الذكاء الاصطناعي مع توثيق أدوات الاسترجاع والتأريض."""
    class SenderType(models.TextChoices):
        USER = "user", "المستخدم"
        ASSISTANT = "assistant", "المساعد الذكي"
        SYSTEM = "system", "رسالة النظام والتعليمات"

    session = models.ForeignKey(
        AIChatSession,
        verbose_name="جلسة المحادثة",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField("المرسل", max_length=20, choices=SenderType.choices)
    content = models.TextField("نص الرسالة")
    token_count = models.PositiveIntegerField("عدد التوكنز المستهلكة", default=0)
    grounding_metadata = models.JSONField("بيانات الاسترجاع والتأريض المرجعي (RAG Metadata)", default=dict, blank=True)

    class Meta:
        verbose_name = "رسالة ذكاء اصطناعي"
        verbose_name_plural = "رسائل جلسات الذكاء الاصطناعي"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.sender}: {self.content[:60]}"


class SchoolAIUsagePolicy(UUIDTimestampedModel):
    """حدود وميزانية الذكاء الاصطناعي، مع أسعار يضبطها مالك المدرسة وفق عقد المزود."""

    school = models.OneToOneField(
        "tenants.School", on_delete=models.CASCADE, related_name="ai_usage_policy",
        verbose_name="المدرسة",
    )
    enabled = models.BooleanField("تفعيل الذكاء الاصطناعي", default=False)
    daily_request_limit = models.PositiveIntegerField("الحد اليومي للطلبات", default=50)
    daily_token_limit = models.PositiveIntegerField("الحد اليومي للتوكنز", default=50000)
    monthly_budget_amount = models.DecimalField("الميزانية الشهرية", max_digits=14, decimal_places=4, default=0)
    input_cost_per_1k_tokens = models.DecimalField("تكلفة 1000 توكن إدخال", max_digits=14, decimal_places=8, default=0)
    output_cost_per_1k_tokens = models.DecimalField("تكلفة 1000 توكن إخراج", max_digits=14, decimal_places=8, default=0)
    currency = models.CharField("العملة", max_length=3, default="USD")
    max_output_tokens = models.PositiveIntegerField("أقصى توكنز إخراج للطلب", default=4000)

    class Meta:
        verbose_name = "سياسة استخدام الذكاء الاصطناعي"
        verbose_name_plural = "سياسات استخدام الذكاء الاصطناعي"

    def clean(self):
        super().clean()
        if self.enabled:
            if self.monthly_budget_amount <= 0:
                raise ValidationError({"monthly_budget_amount": "حدد ميزانية شهرية موجبة قبل تفعيل الذكاء الاصطناعي."})
            if self.input_cost_per_1k_tokens <= 0 and self.output_cost_per_1k_tokens <= 0:
                raise ValidationError("أدخل أسعار التوكنز المعتمدة من مزود النموذج قبل التفعيل.")
            if self.daily_request_limit < 1 or self.daily_token_limit < 1 or self.max_output_tokens < 1:
                raise ValidationError("يجب أن تكون حدود الاستخدام أعداداً موجبة.")

    def __str__(self):
        return f"{self.school} - {'مفعل' if self.enabled else 'معطل'}"


class AIUsageRecord(UUIDTimestampedModel):
    """سجل تكلفة واستهلاك AI بلا حفظ prompt أو محتوى إجابة الطالب."""

    class Status(models.TextChoices):
        STARTED = "started", "قيد التنفيذ"
        SUCCEEDED = "succeeded", "ناجح"
        FAILED = "failed", "فشل"

    school = models.ForeignKey("tenants.School", on_delete=models.PROTECT, related_name="ai_usage_records")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ai_usage_records")
    tool = models.CharField("الأداة", max_length=80, db_index=True)
    model_name = models.CharField("النموذج", max_length=100)
    source_refs = models.JSONField("مراجع مصادر البيانات", default=dict, blank=True)
    input_tokens = models.PositiveIntegerField("توكنز الإدخال المقدرة", default=0)
    output_tokens = models.PositiveIntegerField("توكنز الإخراج المقدرة", default=0)
    estimated_cost = models.DecimalField("التكلفة المقدرة", max_digits=16, decimal_places=8, default=0)
    currency = models.CharField("العملة", max_length=3, default="USD")
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.STARTED, db_index=True)
    failure_code = models.CharField("رمز الفشل", max_length=80, blank=True)
    completed_at = models.DateTimeField("وقت الاكتمال", null=True, blank=True)

    class Meta:
        verbose_name = "سجل استهلاك الذكاء الاصطناعي"
        verbose_name_plural = "سجلات استهلاك الذكاء الاصطناعي"
        indexes = [
            models.Index(fields=["school", "created_at"], name="copilot_ai_school_date"),
            models.Index(fields=["school", "user", "created_at"], name="copilot_ai_user_date"),
        ]

    def __str__(self):
        return f"{self.school} / {self.tool} / {self.estimated_cost} {self.currency}"
