"""Student and guardian domain models."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class Student(TenantOwnedModel):
    """ملف الطالب الأكاديمي والتشغيلي."""
    class Gender(models.TextChoices):
        MALE = "male", "ذكر"
        FEMALE = "female", "أنثى"

    class Status(models.TextChoices):
        ACTIVE = "active", "نشط"
        SUSPENDED = "suspended", "موقوف مؤقتاً"
        WITHDRAWN = "withdrawn", "منسحب"
        GRADUATED = "graduated", "متخرج"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب تسجيل الدخول (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_profiles",
        db_index=True,
    )
    student_id_number = models.CharField("الرقم المدرسي / الأكاديمي", max_length=50, db_index=True)
    first_name = models.CharField("الاسم الأول", max_length=100)
    middle_name = models.CharField("اسم الأب / الجد", max_length=100, blank=True)
    last_name = models.CharField("اسم العائلة", max_length=100)
    national_id = models.CharField("رقم الهوية الوطنية / الإقامة", max_length=50, blank=True)
    birth_date = models.DateField("تاريخ الميلاد", null=True, blank=True)
    gender = models.CharField("الجنس", max_length=10, choices=Gender.choices, default=Gender.MALE)
    
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي الحالي",
        on_delete=models.PROTECT,
        related_name="enrolled_students",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية",
        on_delete=models.PROTECT,
        related_name="enrolled_students",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية الحالية",
        on_delete=models.PROTECT,
        related_name="students",
    )
    enrollment_date = models.DateField("تاريخ الالتحاق بالمدرسة", default=timezone.now)
    status = models.CharField("حالة القيد", max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        verbose_name = "طالب"
        verbose_name_plural = "الطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student_id_number"],
                condition=models.Q(is_archived=False),
                name="students_student_school_id_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "grade_level", "section", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_full_name()} ({self.student_id_number}) - {self.section}"

    def get_full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()

    def clean(self):
        super().clean()
        if self.grade_level_id and self.grade_level.school_id != self.school_id:
            raise ValidationError({"grade_level": "الصف الدراسي لا يتبع نفس المدرسة."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة الصفية لا تتبع نفس المدرسة."})
        if self.section_id and self.grade_level_id and self.section.grade_id != self.grade_level_id:
            raise ValidationError({"section": "الشعبة المحددة لا تنتمي إلى الصف الدراسي المحدد."})


class Guardian(TenantOwnedModel):
    """ملف ولي الأمر وربطه بالحساب المدرسي."""
    class RelationshipType(models.TextChoices):
        FATHER = "father", "أب"
        MOTHER = "mother", "أم"
        BROTHER = "brother", "أخ / أخت"
        UNCLE = "uncle", "عم / خال"
        LEGAL_GUARDIAN = "guardian", "وصي شرعي / كفيل"
        OTHER = "other", "آخر"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب المستخدم لولي الأمر",
        on_delete=models.PROTECT,
        related_name="guardian_profiles",
        db_index=True,
    )
    national_id = models.CharField("رقم الهوية الوطنية / الإقامة", max_length=50, blank=True)
    relationship_type = models.CharField("صلة القرابة", max_length=20, choices=RelationshipType.choices, default=RelationshipType.FATHER)
    occupation = models.CharField("المهنة / جهة العمل", max_length=150, blank=True)
    emergency_phone = models.CharField("هاتف الطوارئ البديل", max_length=25, blank=True)

    class Meta:
        verbose_name = "ولي أمر"
        verbose_name_plural = "أولياء الأمور"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "user"],
                condition=models.Q(is_archived=False),
                name="students_guardian_school_user_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.phone} ({self.get_relationship_type_display()})"


class StudentGuardianRelation(TenantOwnedModel):
    """جدول الربط بين الطلاب وأولياء الأمور مع صلاحيات الاستلام والمتابعة."""
    student = models.ForeignKey(
        Student,
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="guardians",
    )
    guardian = models.ForeignKey(
        Guardian,
        verbose_name="ولي الأمر",
        on_delete=models.CASCADE,
        related_name="students",
    )
    is_primary = models.BooleanField("ولي الأمر الأساسي للمراسلات", default=True)
    receives_notifications = models.BooleanField("يستلم الإشعارات الأكاديمية والمالية", default=True)
    can_pickup = models.BooleanField("مخول باستلام الطالب والانصراف", default=True)

    class Meta:
        verbose_name = "صلة ولي الأمر بالطالب"
        verbose_name_plural = "صلات أولياء الأمور بالطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "guardian"],
                condition=models.Q(is_archived=False),
                name="students_student_guardian_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.guardian} -> {self.student}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.guardian_id and self.guardian.school_id != self.school_id:
            raise ValidationError({"guardian": "ولي الأمر لا يتبع نفس المدرسة."})
