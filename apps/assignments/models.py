"""Homework and assignment domain models."""
from __future__ import annotations

import os

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


def homework_submission_path(instance: HomeworkSubmission, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"schools/{instance.school_id}/homework_submissions/{instance.homework_id}/{instance.student_id}{ext}"


class Homework(TenantOwnedModel):
    """الواجبات والتكليفات المدرسية المسندة من المعلم إلى الشعبة."""
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="homeworks",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية",
        on_delete=models.PROTECT,
        related_name="homeworks",
    )
    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم الذي أسند الواجب",
        on_delete=models.PROTECT,
        related_name="assigned_homeworks",
    )
    title = models.CharField("عنوان الواجب", max_length=255)
    description = models.TextField("تفاصيل التكليف والمطلوب إنجازه")
    assigned_date = models.DateField("تاريخ الإسناد", default=timezone.now)
    due_date = models.DateTimeField("الموعد النهائي للتسليم")
    max_score = models.DecimalField("الدرجة المستحقة", max_digits=6, decimal_places=2, default=10.00)
    is_active = models.BooleanField("الواجب متاح للتسليم", default=True)

    class Meta:
        verbose_name = "واجب مدرسي"
        verbose_name_plural = "الواجبات والتكليفات"
        indexes = [
            models.Index(fields=["school", "section", "due_date"]),
            models.Index(fields=["school", "teacher", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} - {self.subject.name} ({self.section})"

    def clean(self):
        super().clean()
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة لا تتبع نفس المدرسة."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة لا تتبع نفس المدرسة."})
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم لا يتبع نفس المدرسة."})


class HomeworkSubmission(TenantOwnedModel):
    """تسليمات الطلاب للواجبات وتقييمات المعلم."""
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "تم التسليم"
        LATE = "late", "تسليم متأخر"
        GRADED = "graded", "تم التصحيح والتقييم"
        RESUBMIT = "resubmit", "مطلوب إعادة التسليم"

    homework = models.ForeignKey(
        Homework,
        verbose_name="الواجب المدرسي",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المسلّم",
        on_delete=models.CASCADE,
        related_name="homework_submissions",
    )
    submission_text = models.TextField("نص الإجابة / الحل", blank=True)
    attachment = models.FileField("ملف المرفق (PDF/صورة)", upload_to=homework_submission_path, blank=True)
    submitted_at = models.DateTimeField("تاريخ ووقت التسليم", default=timezone.now)
    status = models.CharField("حالة التسليم", max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    
    score = models.DecimalField("الدرجة المحرزة", max_digits=6, decimal_places=2, null=True, blank=True)
    teacher_feedback = models.TextField("ملاحظات المعلم / التقييم الذكي", blank=True)
    graded_by = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المصحح",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="graded_homeworks",
    )
    graded_at = models.DateTimeField("تاريخ التصحيح", null=True, blank=True)

    class Meta:
        verbose_name = "تسليم واجب"
        verbose_name_plural = "تسليمات الواجبات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "homework", "student"],
                condition=models.Q(is_archived=False),
                name="assignments_submission_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "student", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.homework.title} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.homework_id and self.homework.school_id != self.school_id:
            raise ValidationError({"homework": "الواجب لا يتبع نفس المدرسة."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.homework_id and self.student_id and self.student.section_id != self.homework.section_id:
            raise ValidationError({"student": "الطالب لا ينتمي إلى شعبة هذا الواجب المحدد."})
        if self.score is not None and self.homework_id and self.score > self.homework.max_score:
            raise ValidationError({"score": f"الدرجة المحرزة ({self.score}) لا يمكن أن تتجاوز الدرجة العظمى للواجب ({self.homework.max_score})."})

def homework_attempt_upload_path(instance: HomeworkSubmissionAttempt, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return (
        f"schools/{instance.school_id}/homework_attempts/"
        f"{instance.submission_id}/{instance.attempt_number}{ext}"
    )


class HomeworkSubmissionAttempt(TenantOwnedModel):
    """Immutable snapshot of one student submission; later attempts never overwrite it."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "تم التسليم"
        LATE = "late", "تسليم متأخر"

    submission = models.ForeignKey(
        HomeworkSubmission,
        verbose_name="سجل تسليم الواجب",
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveSmallIntegerField("رقم المحاولة")
    submission_text = models.TextField("نص الإجابة في هذه المحاولة", blank=True)
    attachment = models.FileField(
        "مرفق هذه المحاولة",
        upload_to=homework_attempt_upload_path,
        blank=True,
    )
    submitted_at = models.DateTimeField("وقت هذه المحاولة", default=timezone.now)
    status = models.CharField(
        "حالة المحاولة", max_length=20, choices=Status.choices,
        default=Status.SUBMITTED,
    )

    class Meta:
        verbose_name = "محاولة تسليم واجب"
        verbose_name_plural = "سجل محاولات تسليم الواجبات"
        ordering = ["attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "submission", "attempt_number"],
                condition=models.Q(is_archived=False),
                name="assignments_attempt_number_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "submission", "submitted_at"], name="asgn_attempt_idx"),
        ]

    def clean(self):
        super().clean()
        if self.submission_id:
            if self.submission.school_id != self.school_id:
                raise ValidationError({"submission": "سجل التسليم لا يتبع المدرسة نفسها."})
            if self.submission.branch_id != self.branch_id:
                raise ValidationError({"branch": "محاولة التسليم يجب أن تتبع فرع سجل التسليم."})
        if self.attempt_number < 1:
            raise ValidationError({"attempt_number": "رقم المحاولة يجب أن يبدأ من 1."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("محاولة التسليم سجل تاريخي غير قابل للاستبدال أو التعديل.")
        return super().save(*args, **kwargs)
