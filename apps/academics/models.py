"""Foundational school structure: academic years, stages, grades, groups and periods."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TenantOwnedModel


def _validate_related_branch(instance, field_name: str) -> None:
    """Allow shared school records, but never link a row to another branch's data."""
    related = getattr(instance, field_name, None)
    if related is None:
        return
    related_branch_id = getattr(related, "branch_id", None)
    if related_branch_id and related_branch_id != instance.branch_id:
        raise ValidationError({field_name: "السجل المرتبط يتبع فرعاً آخر؛ اختر سجلاً مشتركاً أو من الفرع نفسه."})


class AcademicYear(TenantOwnedModel):
    class Status(models.TextChoices):
        PLANNING = "planning", "قيد الإعداد"
        ACTIVE = "active", "جارية"
        CLOSED = "closed", "مغلقة"
        ARCHIVED = "archived", "مؤرشفة"

    name = models.CharField("اسم السنة الدراسية", max_length=80)
    code = models.CharField("رمز السنة", max_length=24)
    starts_on = models.DateField("تاريخ البداية")
    ends_on = models.DateField("تاريخ النهاية")
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.PLANNING, db_index=True)
    is_current = models.BooleanField("السنة الحالية", default=False)
    opened_at = models.DateTimeField("تاريخ الفتح", null=True, blank=True)
    closed_at = models.DateTimeField("تاريخ الإغلاق", null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        verbose_name = "سنة دراسية"
        verbose_name_plural = "السنوات الدراسية"
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], condition=Q(branch__isnull=True), name="acad_year_code_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "code"], condition=Q(branch__isnull=False), name="acad_year_code_branch_uq"),
            models.UniqueConstraint(fields=["school"], condition=Q(is_current=True, is_archived=False, branch__isnull=True), name="acad_year_curr_global_uq"),
            models.UniqueConstraint(fields=["school", "branch"], condition=Q(is_current=True, is_archived=False, branch__isnull=False), name="acad_year_curr_branch_uq"),
        ]
        indexes = [models.Index(fields=["school", "status", "starts_on"])]

    def __str__(self):
        return f"{self.name} - {self.school}"

    def clean(self):
        super().clean()
        if self.ends_on and self.starts_on and self.ends_on <= self.starts_on:
            raise ValidationError({"ends_on": "تاريخ نهاية السنة يجب أن يكون بعد تاريخ بدايتها."})
        if self.is_current and self.status != self.Status.ACTIVE:
            raise ValidationError({"is_current": "لا يمكن تحديد سنة غير جارية كسنة حالية."})



class AcademicTerm(TenantOwnedModel):
    academic_year = models.ForeignKey(AcademicYear, verbose_name="السنة الدراسية", on_delete=models.PROTECT, related_name="terms")
    name = models.CharField("اسم الفصل الدراسي", max_length=80)
    number = models.PositiveSmallIntegerField("ترتيب الفصل")
    starts_on = models.DateField("البداية")
    ends_on = models.DateField("النهاية")
    is_current = models.BooleanField("الفصل الحالي", default=False)
    is_closed = models.BooleanField("مغلق", default=False)

    class Meta:
        verbose_name = "فصل دراسي"
        verbose_name_plural = "الفصول الدراسية"
        ordering = ["academic_year__starts_on", "number"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "number"], condition=Q(branch__isnull=True), name="acad_term_num_global_uq"),
            models.UniqueConstraint(fields=["academic_year", "branch", "number"], condition=Q(branch__isnull=False), name="acad_term_num_branch_uq"),
            models.UniqueConstraint(fields=["academic_year"], condition=Q(is_current=True, is_archived=False, branch__isnull=True), name="acad_term_curr_global_uq"),
            models.UniqueConstraint(fields=["academic_year", "branch"], condition=Q(is_current=True, is_archived=False, branch__isnull=False), name="acad_term_curr_branch_uq"),
        ]

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"

    def clean(self):
        super().clean()
        if self.academic_year_id and self.school_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة نفسها."})
        _validate_related_branch(self, "academic_year")
        if self.is_current and self.is_closed:
            raise ValidationError({"is_current": "لا يمكن أن يكون الفصل مغلقاً وحالياً في الوقت نفسه."})
        if self.starts_on and self.ends_on and self.ends_on <= self.starts_on:
            raise ValidationError({"ends_on": "تاريخ النهاية يجب أن يكون بعد تاريخ البداية."})
        if self.academic_year_id and self.starts_on and self.ends_on:
            if self.starts_on < self.academic_year.starts_on or self.ends_on > self.academic_year.ends_on:
                raise ValidationError("الفصل الدراسي يجب أن يقع داخل حدود السنة الدراسية.")



class EducationalStage(TenantOwnedModel):
    name = models.CharField("اسم المرحلة", max_length=100)
    code = models.CharField("رمز المرحلة", max_length=24)
    sequence = models.PositiveSmallIntegerField("الترتيب", default=1)
    description = models.TextField("الوصف", blank=True)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "مرحلة تعليمية"
        verbose_name_plural = "المراحل التعليمية"
        ordering = ["school", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], condition=Q(branch__isnull=True), name="acad_stage_code_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "code"], condition=Q(branch__isnull=False), name="acad_stage_code_branch_uq"),
        ]

    def __str__(self):
        return self.name


class GradeLevel(TenantOwnedModel):
    stage = models.ForeignKey(EducationalStage, verbose_name="المرحلة", on_delete=models.PROTECT, related_name="grades")
    name = models.CharField("اسم الصف", max_length=100)
    code = models.CharField("رمز الصف", max_length=24)
    sequence = models.PositiveSmallIntegerField("الترتيب", default=1)
    age_from = models.PositiveSmallIntegerField("أقل عمر", null=True, blank=True)
    age_to = models.PositiveSmallIntegerField("أعلى عمر", null=True, blank=True)
    is_active = models.BooleanField("نشط", default=True)

    class Meta:
        verbose_name = "صف دراسي"
        verbose_name_plural = "الصفوف الدراسية"
        ordering = ["stage__sequence", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], condition=Q(branch__isnull=True), name="acad_grade_code_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "code"], condition=Q(branch__isnull=False), name="acad_grade_code_branch_uq"),
        ]

    def __str__(self):
        return f"{self.stage.name} / {self.name}"

    def clean(self):
        super().clean()
        if self.stage_id and self.school_id and self.stage.school_id != self.school_id:
            raise ValidationError({"stage": "المرحلة المحددة لا تتبع المدرسة نفسها."})
        _validate_related_branch(self, "stage")
        if self.age_from is not None and self.age_to is not None and self.age_to < self.age_from:
            raise ValidationError("الحد الأعلى للعمر لا يمكن أن يكون أقل من الحد الأدنى.")


class Classroom(TenantOwnedModel):
    class Type(models.TextChoices):
        CLASS = "class", "قاعة صفية"
        LAB = "lab", "مختبر"
        COMPUTER = "computer", "مختبر حاسوب"
        LIBRARY = "library", "مكتبة"
        MULTIPURPOSE = "multi", "متعددة الاستخدام"

    code = models.CharField("رمز القاعة", max_length=24)
    name = models.CharField("اسم القاعة", max_length=100)
    classroom_type = models.CharField("نوع القاعة", max_length=12, choices=Type.choices, default=Type.CLASS)
    capacity = models.PositiveSmallIntegerField("السعة", default=30)
    building = models.CharField("المبنى", max_length=80, blank=True)
    floor = models.CharField("الطابق", max_length=30, blank=True)
    has_projector = models.BooleanField("جهاز عرض", default=False)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "قاعة / غرفة"
        verbose_name_plural = "القاعات والغرف"
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], condition=Q(branch__isnull=True), name="acad_room_code_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "code"], condition=Q(branch__isnull=False), name="acad_room_code_branch_uq"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        super().clean()
        if self.capacity < 1:
            raise ValidationError({"capacity": "سعة القاعة يجب أن تكون أكبر من صفر."})


class Section(TenantOwnedModel):
    academic_year = models.ForeignKey(AcademicYear, verbose_name="السنة الدراسية", on_delete=models.PROTECT, related_name="sections")
    grade = models.ForeignKey(GradeLevel, verbose_name="الصف", on_delete=models.PROTECT, related_name="sections")
    code = models.CharField("رمز الشعبة", max_length=24)
    name = models.CharField("اسم الشعبة", max_length=100)
    homeroom_classroom = models.ForeignKey(Classroom, verbose_name="القاعة الأساسية", null=True, blank=True, on_delete=models.PROTECT, related_name="homeroom_sections")
    capacity = models.PositiveSmallIntegerField("السعة القصوى", default=35)
    floor_wing = models.CharField("الدور / الجناح (مثل: الدور الأول، جناح أ)", max_length=100, blank=True)
    supervisor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المشرف المسؤول عن الحضور والمتابعة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supervised_sections",
    )
    is_active = models.BooleanField("نشطة", default=True)
    notes = models.CharField("ملاحظات", max_length=500, blank=True)

    class Meta:
        verbose_name = "شعبة / فصل"
        verbose_name_plural = "الشعب والفصول"
        ordering = ["academic_year__starts_on", "grade__sequence", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "academic_year", "code"], condition=Q(branch__isnull=True), name="acad_section_code_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "academic_year", "code"], condition=Q(branch__isnull=False), name="acad_section_code_branch_uq"),
        ]
        indexes = [models.Index(fields=["school", "academic_year", "grade"])]

    def __str__(self):
        return f"{self.grade.name} - {self.name}"

    @property
    def current_student_count(self) -> int:
        """العدد الفعلي للطلاب المقيدين في الشعبة."""
        return self.enrolled_students.filter(is_archived=False).count()

    @property
    def is_full(self) -> bool:
        """هل امتلأت الطاقة الاستيعابية للشعبة ويلزم فتح شعبة جديدة؟"""
        return self.current_student_count >= self.capacity

    @property
    def available_seats(self) -> int:
        """عدد المقاعد الشاغرة المتبقية في الشعبة."""
        return max(0, self.capacity - self.current_student_count)

    def clean(self):
        super().clean()
        if self.capacity < 1:
            raise ValidationError({"capacity": "السعة القصوى للشعبة يجب أن تكون أكبر من صفر."})
        for field_name in ("academic_year", "grade", "homeroom_classroom"):
            obj = getattr(self, field_name, None)
            if obj and self.school_id and obj.school_id != self.school_id:
                raise ValidationError({field_name: "السجل المرتبط لا يتبع المدرسة نفسها."})
            _validate_related_branch(self, field_name)



class Subject(TenantOwnedModel):
    code = models.CharField("رمز المادة", max_length=24)
    name = models.CharField("اسم المادة", max_length=120)
    short_name = models.CharField("الاسم المختصر", max_length=40, blank=True)
    description = models.TextField("الوصف", blank=True)
    is_core = models.BooleanField("مادة أساسية", default=True)
    default_weekly_periods = models.PositiveSmallIntegerField("الحصص الأسبوعية الافتراضية", default=2)
    max_score = models.DecimalField("الدرجة النهائية الافتراضية", max_digits=7, decimal_places=2, default=100)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "مادة دراسية"
        verbose_name_plural = "المواد الدراسية"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], condition=Q(branch__isnull=True), name="acad_subject_code_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "code"], condition=Q(branch__isnull=False), name="acad_subject_code_branch_uq"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.max_score <= 0:
            raise ValidationError({"max_score": "الدرجة النهائية يجب أن تكون أكبر من صفر."})


class PeriodDefinition(TenantOwnedModel):
    class Kind(models.TextChoices):
        LESSON = "lesson", "حصة دراسية"
        BREAK = "break", "استراحة"
        ASSEMBLY = "assembly", "طابور / نشاط"

    name = models.CharField("اسم الفترة", max_length=60)
    period_number = models.PositiveSmallIntegerField("رقم الحصة / الفترة")
    starts_at = models.TimeField("وقت البداية")
    ends_at = models.TimeField("وقت النهاية")
    kind = models.CharField("نوع الفترة", max_length=12, choices=Kind.choices, default=Kind.LESSON)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "فترة / حصة زمنية"
        verbose_name_plural = "الفترات والحصص الزمنية"
        ordering = ["period_number"]
        constraints = [
            models.UniqueConstraint(fields=["school", "period_number"], condition=Q(branch__isnull=True), name="acad_period_num_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "period_number"], condition=Q(branch__isnull=False), name="acad_period_num_branch_uq"),
        ]

    def __str__(self):
        return f"{self.period_number}. {self.name} ({self.starts_at:%H:%M}-{self.ends_at:%H:%M})"

    def clean(self):
        super().clean()
        if self.period_number < 1:
            raise ValidationError({"period_number": "رقم الفترة يجب أن يبدأ من 1."})
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "وقت نهاية الفترة يجب أن يكون بعد وقت بدايتها."})
        if self.is_active and self.school_id and self.starts_at and self.ends_at and self.ends_at > self.starts_at:
            overlaps = PeriodDefinition.objects.filter(
                school_id=self.school_id,
                is_archived=False,
                is_active=True,
                starts_at__lt=self.ends_at,
                ends_at__gt=self.starts_at,
            ).exclude(pk=self.pk)
            if self.branch_id:
                overlaps = overlaps.filter(Q(branch_id=self.branch_id) | Q(branch__isnull=True))
            if overlaps.exists():
                raise ValidationError({"starts_at": "الفترة الزمنية تتداخل مع فترة نشطة أخرى في النطاق نفسه."})


class SchoolWorkingDay(TenantOwnedModel):
    WEEKDAYS = [(0, "الاثنين"), (1, "الثلاثاء"), (2, "الأربعاء"), (3, "الخميس"), (4, "الجمعة"), (5, "السبت"), (6, "الأحد")]
    weekday = models.PositiveSmallIntegerField("يوم الأسبوع", choices=WEEKDAYS)
    is_working = models.BooleanField("يوم دوام", default=True)
    sequence = models.PositiveSmallIntegerField("ترتيب اليوم", default=1)
    first_period = models.ForeignKey(PeriodDefinition, verbose_name="أول فترة", null=True, blank=True, on_delete=models.PROTECT, related_name="first_days")
    last_period = models.ForeignKey(PeriodDefinition, verbose_name="آخر فترة", null=True, blank=True, on_delete=models.PROTECT, related_name="last_days")

    class Meta:
        verbose_name = "يوم دوام"
        verbose_name_plural = "أيام الدوام الأسبوعية"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["school", "weekday"], condition=Q(branch__isnull=True), name="acad_workday_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "weekday"], condition=Q(branch__isnull=False), name="acad_workday_branch_uq"),
        ]

    def __str__(self):
        return self.get_weekday_display()

    def clean(self):
        super().clean()
        if self.sequence < 1:
            raise ValidationError({"sequence": "ترتيب يوم الدوام يجب أن يبدأ من 1."})
        for field_name in ("first_period", "last_period"):
            obj = getattr(self, field_name, None)
            if obj and self.school_id and obj.school_id != self.school_id:
                raise ValidationError({field_name: "الفترة الزمنية لا تتبع المدرسة نفسها."})
            _validate_related_branch(self, field_name)
            if obj and (obj.is_archived or not obj.is_active):
                raise ValidationError({field_name: "لا يمكن ربط يوم الدوام بفترة غير نشطة أو مؤرشفة."})
        if self.first_period_id and self.last_period_id:
            if self.first_period.period_number > self.last_period.period_number:
                raise ValidationError({"last_period": "يجب أن تكون آخر فترة بعد أول فترة أو مساوية لها."})
