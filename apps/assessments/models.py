"""Assessment, gradebook, and exam control domain models."""
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


# -----------------------------------------------------------------------------
# Exam Control Room, Seating, and Committees (كنترول الاختبارات ولجان الامتحانات)
# -----------------------------------------------------------------------------

class ExamCommittee(TenantOwnedModel):
    """لجان سير الامتحانات وقاعات الكنترول."""
    name = models.CharField("اسم اللجنة / القاعة", max_length=150)
    committee_number = models.CharField("رقم اللجنة", max_length=50)
    location_room = models.CharField("موقع اللجنة / القاعة", max_length=150)
    capacity = models.PositiveSmallIntegerField("السعة القصوى للجنة", default=25)
    head_supervisor = models.ForeignKey(
        "staff.Teacher",
        verbose_name="رئيس اللجنة والمراقب الأول",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_committees",
    )

    class Meta:
        verbose_name = "لجنة اختبارات (كنترول)"
        verbose_name_plural = "لجان الامتحانات والكنترول"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "committee_number"],
                condition=models.Q(is_archived=False),
                name="assessments_committee_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"لجنة #{self.committee_number} - {self.name} ({self.location_room})"


class ExamSeating(TenantOwnedModel):
    """أرقام الجلوس والأرقام السرية للطلاب في الكنترول."""
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="exam_seatings",
    )
    committee = models.ForeignKey(
        ExamCommittee,
        verbose_name="لجنة الاختبار",
        on_delete=models.PROTECT,
        related_name="seatings",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="exam_seatings",
    )
    seating_number = models.PositiveIntegerField("رقم الجلوس المعلن")
    secret_code = models.CharField("الرقم السري للكنترول (للتصحيح المعمى)", max_length=50, blank=True)

    class Meta:
        verbose_name = "رقم جلوس طالب"
        verbose_name_plural = "أرقام الجلوس والكنترول"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "seating_number"],
                condition=models.Q(is_archived=False),
                name="assessments_seating_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "academic_year", "student"],
                condition=models.Q(is_archived=False),
                name="assessments_student_year_seating_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"رقم جلوس ({self.seating_number}) - {self.student} [لجنة: {self.committee.name}]"
