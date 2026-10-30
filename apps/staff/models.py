"""Staff and teacher domain models."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class Teacher(TenantOwnedModel):
    """ملف المعلم التشغيلي التابع لمدرسة محددة."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب المستخدم",
        on_delete=models.PROTECT,
        related_name="teacher_profiles",
        db_index=True,
    )
    employee_number = models.CharField("الرقم الوظيفي", max_length=50, blank=True)
    specialization = models.CharField("التخصص التدريسي", max_length=150)
    qualifications = models.TextField("المؤهلات العلمية", blank=True)
    hire_date = models.DateField("تاريخ التعيين", default=timezone.now)
    max_weekly_periods = models.PositiveSmallIntegerField("النصاب الأقصى للحصص الأسبوعية", default=24)
    is_active_teaching = models.BooleanField("على رأس العمل التدريسي", default=True)

    class Meta:
        verbose_name = "معلم"
        verbose_name_plural = "المعلمون"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "user"],
                condition=models.Q(is_archived=False),
                name="staff_teacher_school_user_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "is_active_teaching"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.phone} - {self.specialization}"


class TeacherAssignment(TenantOwnedModel):
    """إسناد المواد والشعب الدراسية للمعلمين."""
    teacher = models.ForeignKey(
        Teacher,
        verbose_name="المعلم",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="teacher_assignments",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية",
        on_delete=models.PROTECT,
        related_name="teacher_assignments",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="teacher_assignments",
    )
    weekly_periods = models.PositiveSmallIntegerField("عدد الحصص الأسبوعية", default=4)

    class Meta:
        verbose_name = "إسناد مادة للمعلم"
        verbose_name_plural = "إسنادات المواد والمعلمين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "teacher", "subject", "section"],
                condition=models.Q(is_archived=False),
                name="staff_teacher_assignment_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.teacher} -> {self.subject.name} ({self.section})"

    def clean(self):
        super().clean()
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم المحدد لا يتبع نفس المدرسة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة المحددة لا تتبع نفس المدرسة."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة المحددة لا تتبع نفس المدرسة."})
