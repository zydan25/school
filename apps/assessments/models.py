"""Assessment and gradebook domain models."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class AssessmentType(TenantOwnedModel):
    """أنواع التقييمات والاختبارات المعتمدة في المدرسة."""
    name = models.CharField("نوع التقييم", max_length=100)
    code = models.CharField("رمز التقييم", max_length=50)
    default_max_score = models.DecimalField("الدرجة العظمى الافتراضية", max_digits=6, decimal_places=2, default=100.00)
    weight_percentage = models.DecimalField("الوزن النسبي (%)", max_digits=5, decimal_places=2, default=20.00)

    class Meta:
        verbose_name = "نوع تقييم"
        verbose_name_plural = "أنواع التقييمات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="assessments_type_school_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.weight_percentage}%)"


class GradeBook(TenantOwnedModel):
    """سجل رصد الدرجات والتقييمات للطلاب."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.PROTECT,
        related_name="grade_records",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="grade_records",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        verbose_name="الفصل الدراسي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="grade_records",
    )
    assessment_type = models.ForeignKey(
        AssessmentType,
        verbose_name="نوع التقييم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="grades",
    )
    homework = models.ForeignKey(
        "assignments.Homework",
        verbose_name="الواجب المرتبط (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gradebook_entries",
    )
    assessment_title = models.CharField("عنوان التقييم / الاختبار", max_length=255)
    score = models.DecimalField("الدرجة المحصلة", max_digits=6, decimal_places=2)
    max_score = models.DecimalField("الدرجة العظمى", max_digits=6, decimal_places=2, default=100.00)
    teacher_feedback = models.TextField("ملاحظات المعلم / تقرير الذكاء الاصطناعي", blank=True)
    graded_by = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم الراصد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="graded_records",
    )
    graded_at = models.DateTimeField("تاريخ الرصد والتقييم", default=timezone.now)
    is_published = models.BooleanField("منشورة للطالب وولي الأمر", default=True)

    class Meta:
        verbose_name = "سجل درجات"
        verbose_name_plural = "دفتر الدرجات والنتائج"
        indexes = [
            models.Index(fields=["school", "student", "subject"]),
            models.Index(fields=["school", "student", "is_published"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.assessment_title}: {self.score}/{self.max_score}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة لا تتبع نفس المدرسة."})
