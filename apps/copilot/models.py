"""AI Copilot (Teacher & Student) models and grounding persistence."""
from __future__ import annotations

import os
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TenantOwnedModel


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
