"""Timetable, Bell Schedule, and scheduled lesson models."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from django.conf import settings

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class WeekDay(models.IntegerChoices):
    SUNDAY = 1, "الأحد"
    MONDAY = 2, "الاثنين"
    TUESDAY = 3, "الثلاثاء"
    WEDNESDAY = 4, "الأربعاء"
    THURSDAY = 5, "الخميس"
    FRIDAY = 6, "الجمعة"
    SATURDAY = 7, "السبت"


class SchoolBellSchedule(TenantOwnedModel):
    """
    قالب توقيت وهيكلية اليوم الدراسي لكل مدرسة.
    يحدد مواعيد بداية ونهاية اليوم، طابور الصباح، عدد الحصص، وأوقات الفسح والصلوات.
    يدعم تخصيص كل مدرسة لجدولها أو اعتماد توقيت الإدارة الافتراضي.
    """
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="bell_schedules",
    )
    name = models.CharField("اسم قالب التوقيت (مثل: التوقيت القياسي، الشتوي، رمضان)", max_length=150)
    is_active = models.BooleanField("مفعل", default=True)
    is_default = models.BooleanField("القالب الافتراضي للمدرسة", default=True)

    # 1. إعدادات طابور الصباح والإذاعة المدرسية
    has_morning_assembly = models.BooleanField("تفعيل الطابور الصباحي والإذاعة", default=True)
    assembly_start_time = models.TimeField("وقت بداية الطابور الصباحي", default=time(7, 15))
    assembly_end_time = models.TimeField("وقت نهاية الطابور الصباحي", default=time(7, 30))

    # 2. إعدادات اليوم الدراسي والحصص
    day_start_time = models.TimeField("وقت بداية اليوم الدراسي", default=time(7, 15))
    day_end_time = models.TimeField("وقت نهاية اليوم الدراسي", default=time(13, 30))
    periods_per_day = models.PositiveSmallIntegerField("عدد الحصص المقررة في اليوم", default=7)
    period_duration_minutes = models.PositiveSmallIntegerField("المدة الافتراضية للحصة (بالدقائق)", default=45)
    passing_duration_minutes = models.PositiveSmallIntegerField("مدة التبديل بين الحصص (بالدقائق)", default=5)

    # 3. إعدادات الفسحة والراحة
    break_duration_minutes = models.PositiveSmallIntegerField("مدة الفسحة الأولى (بالدقائق)", default=25)
    break_after_period = models.PositiveSmallIntegerField("الفسحة الأولى بعد الحصة رقم", default=3)
    has_second_break = models.BooleanField("تفعيل فسحة ثانية / استراحة صلاة الظهر", default=False)
    second_break_after_period = models.PositiveSmallIntegerField("الفسحة الثانية بعد الحصة رقم", default=5)
    second_break_duration_minutes = models.PositiveSmallIntegerField("مدة الفسحة الثانية / الصلاة (بالدقائق)", default=20)

    notes = models.TextField("ملاحظات إدارية عن التوقيت", blank=True)

    class Meta:
        verbose_name = "قالب مواعيد وتوقيت الحصص"
        verbose_name_plural = "قوالب مواعيد الحصص واليوم الدراسي"
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "academic_year", "name"], condition=models.Q(is_archived=False, branch__isnull=True), name="tt_bell_name_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "academic_year", "name"], condition=models.Q(is_archived=False, branch__isnull=False), name="tt_bell_name_branch_uq"),
            models.UniqueConstraint(fields=["school", "academic_year"], condition=models.Q(is_archived=False, is_active=True, is_default=True, branch__isnull=True), name="tt_bell_default_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "academic_year"], condition=models.Q(is_archived=False, is_active=True, is_default=True, branch__isnull=False), name="tt_bell_default_branch_uq"),
        ]

    def __str__(self) -> str:
        default_tag = " (افتراضي)" if self.is_default else ""
        return f"{self.name} - {self.school.name}{default_tag}"

    def clean(self):
        super().clean()
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})
        if self.academic_year_id and self.academic_year.branch_id and self.academic_year.branch_id != self.branch_id:
            raise ValidationError({"academic_year": "قالب الجرس يجب أن يتبع فرع السنة الدراسية."})

        if self.day_start_time and self.day_end_time and self.day_start_time >= self.day_end_time:
            raise ValidationError({"day_end_time": "وقت نهاية اليوم الدراسي يجب أن يكون بعد وقت البداية."})

        if self.has_morning_assembly:
            if self.assembly_start_time >= self.assembly_end_time:
                raise ValidationError({"assembly_end_time": "وقت نهاية الطابور يجب أن يكون بعد وقت بدايته."})
            if self.assembly_start_time < self.day_start_time or self.assembly_end_time > self.day_end_time:
                raise ValidationError({"assembly_start_time": "وقت الطابور الصباحي يجب أن يقع ضمن حدود اليوم الدراسي."})

        if self.periods_per_day < 1 or self.periods_per_day > 14:
            raise ValidationError({"periods_per_day": "عدد الحصص في اليوم يجب أن يكون بين 1 و 14 حصة."})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_default and self.is_active and self.school_id:
                SchoolBellSchedule.objects.select_for_update().filter(
                    school_id=self.school_id, academic_year_id=self.academic_year_id,
                    branch_id=self.branch_id, is_default=True, is_active=True, is_archived=False,
                ).exclude(pk=self.pk).update(is_default=False)
            return super().save(*args, **kwargs)


class SchedulePeriodTemplate(TenantOwnedModel):
    """
    الفترات الزمنية المعتمدة لكل حصة أو طابور أو استراحة ضمن قالب المواعيد.
    تمنع بشكل صارم حدوث أي تداخل زمني بين حصة وأخرى أو بين حصة وطابور أو وقت راحة.
    """
    class PeriodType(models.TextChoices):
        ASSEMBLY = "assembly", "طابور صباحي وإذاعة مدرسية"
        PERIOD = "period", "حصة دراسية"
        BREAK = "break", "استراحة / فسحة أولى"
        PRAYER_BREAK = "prayer_break", "استراحة صلاة الظهر / فسحة ثانية"
        ACTIVITY = "activity", "نشاط مدرسي / حلقة إرشاد"

    schedule = models.ForeignKey(
        SchoolBellSchedule,
        verbose_name="قالب التوقيت التابع له",
        on_delete=models.CASCADE,
        related_name="period_templates",
    )
    period_type = models.CharField(
        "نوع الفترة",
        max_length=20,
        choices=PeriodType.choices,
        default=PeriodType.PERIOD,
    )
    period_number = models.PositiveSmallIntegerField("رقم الحصة في اليوم", null=True, blank=True)
    name = models.CharField("اسم الحصة / الفترة", max_length=100)
    start_time = models.TimeField("وقت البداية")
    end_time = models.TimeField("وقت النهاية")
    day_of_week = models.PositiveSmallIntegerField(
        "اليوم المخصص (أو اتركه فارغاً للتعميم على كافة الأيام)",
        choices=WeekDay.choices,
        null=True,
        blank=True,
    )
    order = models.PositiveSmallIntegerField("الترتيب التسلسلي", default=1)
    is_active = models.BooleanField("مفعلة", default=True)

    class Meta:
        verbose_name = "فترة توقيت / حصة"
        verbose_name_plural = "فترات وتوقيت الحصص والاستراحات"
        ordering = ["schedule", "order", "start_time"]
        indexes = [
            models.Index(fields=["school", "schedule", "period_type"]),
            models.Index(fields=["school", "schedule", "day_of_week"]),
        ]

    def __str__(self) -> str:
        day_str = f" [{self.get_day_of_week_display()}]" if self.day_of_week else " [يومياً]"
        return f"{self.name}{day_str} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

    def clean(self):
        super().clean()
        if self.schedule_id and self.schedule.school_id != self.school_id:
            raise ValidationError({"schedule": "قالب التوقيت المحدد لا يتبع نفس المدرسة."})
        if self.schedule_id and self.schedule.branch_id and self.schedule.branch_id != self.branch_id:
            raise ValidationError({"schedule": "الفترة يجب أن تتبع فرع قالب الجرس نفسه."})
        if self.schedule_id and self.period_type == self.PeriodType.PERIOD:
            if self.period_number is None or not 1 <= self.period_number <= self.schedule.periods_per_day:
                raise ValidationError({"period_number": "رقم الحصة خارج عدد الحصص المحدد في قالب الجرس."})
        elif self.period_type != self.PeriodType.PERIOD and self.period_number is not None:
            raise ValidationError({"period_number": "لا تحدد رقم حصة لفترة طابور أو استراحة أو نشاط."})
        if self.schedule_id and not (self.schedule.day_start_time <= self.start_time < self.end_time <= self.schedule.day_end_time):
            raise ValidationError({"start_time": "الفترة يجب أن تقع بالكامل داخل حدود اليوم الدراسي."})

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "وقت نهاية الفترة يجب أن يكون بعد وقت بدايتها."})

        if self.period_type == self.PeriodType.PERIOD and not self.period_number:
            raise ValidationError({"period_number": "يجب تحديد رقم الحصة عند اختيار نوع الفترة كحصة دراسية."})

        # فحص ومنع التداخل الزمني الصارم مع أي حصة أخرى أو وقت طابور أو استراحة
        if self.schedule_id and self.start_time and self.end_time:
            conflicts_qs = SchedulePeriodTemplate.objects.filter(
                school_id=self.school_id,
                schedule_id=self.schedule_id,
                is_active=True,
                is_archived=False,
            ).exclude(pk=self.pk)

            # إذا كانت الفترة مخصصة ليوم معين، نفحص الفترات العامة أو المخصصة لنفس اليوم
            if self.day_of_week is not None:
                conflicts_qs = conflicts_qs.filter(
                    models.Q(day_of_week__isnull=True) | models.Q(day_of_week=self.day_of_week)
                )

            for other in conflicts_qs:
                # التحقق من شرط التداخل الزمني: max(s1, s2) < min(e1, e2)
                overlap = max(self.start_time, other.start_time) < min(self.end_time, other.end_time)
                if overlap:
                    raise ValidationError(
                        f"تعارض وتداخل زمني غير مسموح: الفترة '{self.name}' ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}) "
                        f"تتداخل في الوقت مع '{other.name}' ({other.start_time.strftime('%H:%M')} - {other.end_time.strftime('%H:%M')}). "
                        f"يمنع النظام تداخل الحصص مع بعضها أو تداخل الحصص مع الطابور الصباحي وأوقات الراحة والفسح."
                    )


class TimetablePlan(TenantOwnedModel):
    """نسخة من الجدول الأسبوعي تمر بدورة مراجعة واعتماد ونشر مؤرخة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        IN_REVIEW = "in_review", "قيد المراجعة"
        APPROVED = "approved", "معتمدة للنشر"
        PUBLISHED = "published", "منشورة ونافذة"
        RETIRED = "retired", "منتهية"

    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.PROTECT, related_name="timetable_plans")
    academic_term = models.ForeignKey("academics.AcademicTerm", on_delete=models.PROTECT, null=True, blank=True, related_name="timetable_plans")
    bell_schedule = models.ForeignKey(SchoolBellSchedule, on_delete=models.PROTECT, null=True, blank=True, related_name="timetable_plans")
    based_on = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="derived_versions")
    name = models.CharField(max_length=150)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False, db_index=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_timetable_plans")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_timetable_plans")
    approved_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="published_timetable_plans")
    published_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-academic_year__starts_on", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["school", "academic_year", "version"], condition=models.Q(is_archived=False, branch__isnull=True), name="tt_plan_version_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "academic_year", "version"], condition=models.Q(is_archived=False, branch__isnull=False), name="tt_plan_version_branch_uq"),
            models.UniqueConstraint(fields=["school", "academic_year"], condition=models.Q(is_archived=False, status="published", is_current=True, branch__isnull=True), name="tt_plan_current_global_uq"),
            models.UniqueConstraint(fields=["school", "branch", "academic_year"], condition=models.Q(is_archived=False, status="published", is_current=True, branch__isnull=False), name="tt_plan_current_branch_uq"),
        ]
        indexes = [models.Index(fields=["school", "academic_year", "status"], name="tt_plan_school_status_idx")]

    def clean(self):
        super().clean()
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة المحددة."})
        if self.academic_year_id and self.academic_year.branch_id and self.academic_year.branch_id != self.branch_id:
            raise ValidationError({"branch": "نسخة الجدول يجب أن تتبع فرع السنة الدراسية."})
        if self.academic_term_id and (self.academic_term.school_id != self.school_id or self.academic_term.academic_year_id != self.academic_year_id):
            raise ValidationError({"academic_term": "الفصل الدراسي لا يتبع السنة والمدرسة للنسخة."})
        if self.bell_schedule_id and (self.bell_schedule.school_id != self.school_id or self.bell_schedule.academic_year_id != self.academic_year_id):
            raise ValidationError({"bell_schedule": "قالب الجرس لا يتبع السنة والمدرسة للنسخة."})
        if self.bell_schedule_id and self.bell_schedule.branch_id and self.bell_schedule.branch_id != self.branch_id:
            raise ValidationError({"bell_schedule": "قالب الجرس يتبع فرعاً مختلفاً."})
        if self.based_on_id and (self.based_on.school_id != self.school_id or self.based_on.academic_year_id != self.academic_year_id or self.based_on.branch_id != self.branch_id):
            raise ValidationError({"based_on": "النسخة المصدر يجب أن تتبع المدرسة والسنة والفرع نفسه."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "تاريخ نهاية السريان يسبق تاريخ بدايته."})
        if self.academic_year_id and not (self.academic_year.starts_on <= self.effective_from <= self.academic_year.ends_on):
            raise ValidationError({"effective_from": "تاريخ السريان يجب أن يقع داخل السنة الدراسية."})
        if self.effective_to and self.academic_year_id and self.effective_to > self.academic_year.ends_on:
            raise ValidationError({"effective_to": "تاريخ نهاية السريان يتجاوز نهاية السنة الدراسية."})
        if self.is_current and self.status != self.Status.PUBLISHED:
            raise ValidationError({"is_current": "لا يمكن جعل نسخة غير منشورة هي النسخة الحالية."})


class ClassSchedule(TenantOwnedModel):
    """الجدول الأسبوعي المعتمد للحصص المدرسية."""
    class WeekDay(models.IntegerChoices):
        SUNDAY = 1, "الأحد"
        MONDAY = 2, "الاثنين"
        TUESDAY = 3, "الثلاثاء"
        WEDNESDAY = 4, "الأربعاء"
        THURSDAY = 5, "الخميس"
        FRIDAY = 6, "الجمعة"
        SATURDAY = 7, "السبت"

    timetable_plan = models.ForeignKey(
        TimetablePlan, null=True, blank=True, on_delete=models.PROTECT,
        related_name="class_schedules", verbose_name="نسخة الجدول المعتمدة",
    )
    bell_schedule = models.ForeignKey(
        SchoolBellSchedule,
        verbose_name="قالب توقيت الحصص المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="class_schedules",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        verbose_name="الفصل الدراسي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية",
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المدرس للحصة",
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    classroom = models.ForeignKey(
        "academics.Classroom",
        verbose_name="القاعة / الغرفة المخصصة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="schedules",
    )
    day_of_week = models.PositiveSmallIntegerField("يوم الحصة", choices=WeekDay.choices)
    period_number = models.PositiveSmallIntegerField("رقم الحصة في اليوم")
    start_time = models.TimeField("وقت بداية الحصة")
    end_time = models.TimeField("وقت نهاية الحصة")

    class Meta:
        verbose_name = "حصة دراسية مجدولة"
        verbose_name_plural = "جدول الحصص المدرسية"
        constraints = [
            models.UniqueConstraint(fields=["school", "academic_year", "section", "day_of_week", "period_number"], condition=models.Q(is_archived=False, timetable_plan__isnull=True), name="tt_sched_legacy_section_uq"),
            models.UniqueConstraint(fields=["school", "academic_year", "teacher", "day_of_week", "period_number"], condition=models.Q(is_archived=False, timetable_plan__isnull=True), name="tt_sched_legacy_teacher_uq"),
            models.UniqueConstraint(fields=["timetable_plan", "section", "day_of_week", "period_number"], condition=models.Q(is_archived=False, timetable_plan__isnull=False), name="tt_sched_plan_section_uq"),
            models.UniqueConstraint(fields=["timetable_plan", "teacher", "day_of_week", "period_number"], condition=models.Q(is_archived=False, timetable_plan__isnull=False), name="tt_sched_plan_teacher_uq"),
        ]
        indexes = [
            models.Index(fields=["school", "section", "day_of_week"]),
            models.Index(fields=["school", "teacher", "day_of_week"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_day_of_week_display()} [حصة {self.period_number}]: {self.subject.name} - {self.section}"

    def clean(self):
        super().clean()

        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})
        if self.section_id:
            if self.section.school_id != self.school_id:
                raise ValidationError({"section": "الشعبة المحددة لا تتبع نفس المدرسة."})
            if self.section.academic_year_id != self.academic_year_id:
                raise ValidationError({"section": "الشعبة لا تتبع السنة الدراسية المحددة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة المحددة لا تتبع نفس المدرسة."})
        if self.teacher_id:
            if self.teacher.school_id != self.school_id:
                raise ValidationError({"teacher": "المعلم المحدد لا يتبع نفس المدرسة."})
            if not self.teacher.is_active_teaching:
                raise ValidationError({"teacher": "لا يمكن جدولة حصص لمعلم غير نشط تدريسياً."})
        if self.classroom_id and self.classroom.school_id != self.school_id:
            raise ValidationError({"classroom": "القاعة المحددة لا تتبع نفس المدرسة."})
        if self.academic_term_id:
            if self.academic_term.school_id != self.school_id or self.academic_term.academic_year_id != self.academic_year_id:
                raise ValidationError({"academic_term": "الفصل الدراسي لا يتبع المدرسة والسنة المحددتين."})
            if self.academic_term.is_closed:
                raise ValidationError({"academic_term": "لا يمكن تعديل جدول مرتبط بفصل دراسي مغلق."})
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "وقت نهاية الحصة يجب أن يكون بعد وقت البداية."})
        if self.period_number < 1:
            raise ValidationError({"period_number": "رقم الحصة يجب أن يبدأ من 1."})

        if self.timetable_plan_id:
            if self.timetable_plan.school_id != self.school_id or self.timetable_plan.academic_year_id != self.academic_year_id:
                raise ValidationError({"timetable_plan": "نسخة الجدول لا تتبع المدرسة والسنة المحددتين."})
            if self.timetable_plan.status != TimetablePlan.Status.DRAFT:
                raise ValidationError({"timetable_plan": "لا يمكن تعديل حصص نسخة بعد إرسالها للمراجعة أو اعتمادها أو نشرها."})
            if self.timetable_plan.academic_term_id and self.academic_term_id != self.timetable_plan.academic_term_id:
                raise ValidationError({"academic_term": "الفصل لا يطابق نطاق نسخة الجدول."})
            if self.branch_id != self.timetable_plan.branch_id:
                raise ValidationError({"branch": "فرع الحصة يجب أن يطابق فرع نسخة الجدول."})

        branch_ids = {
            value for value in (
                self.section.branch_id if self.section_id else None,
                self.teacher.branch_id if self.teacher_id else None,
                self.classroom.branch_id if self.classroom_id else None,
                self.bell_schedule.branch_id if self.bell_schedule_id else None,
                self.timetable_plan.branch_id if self.timetable_plan_id else None,
            ) if value
        }
        if len(branch_ids) > 1:
            raise ValidationError("الحصة تربط موارد من فروع مختلفة.")
        if branch_ids:
            required_branch_id = next(iter(branch_ids))
            if self.branch_id and self.branch_id != required_branch_id:
                raise ValidationError({"branch": "فرع الحصة لا يطابق فرع الموارد المرتبطة."})
            if not self.branch_id:
                self.branch_id = required_branch_id

        if self.bell_schedule_id:
            if self.bell_schedule.school_id != self.school_id or self.bell_schedule.academic_year_id != self.academic_year_id:
                raise ValidationError({"bell_schedule": "قالب الجرس لا يتبع المدرسة والسنة المحددتين."})
            if self.bell_schedule.branch_id and self.bell_schedule.branch_id != self.branch_id:
                raise ValidationError({"bell_schedule": "قالب الجرس يتبع فرعاً مختلفاً."})

        # Convert Python weekday (Monday=0) to timetable weekday (Sunday=1).
        from apps.academics.models import SchoolWorkingDay
        python_weekday = (self.day_of_week - 2) % 7
        configured_days = SchoolWorkingDay.objects.filter(
            school=self.school, weekday=python_weekday, is_archived=False,
        )
        if self.branch_id:
            working_day = (
                configured_days.filter(branch_id=self.branch_id).first()
                or configured_days.filter(branch__isnull=True).first()
            )
        else:
            working_day = configured_days.filter(branch__isnull=True).first()
        if working_day and not working_day.is_working:
            raise ValidationError({"day_of_week": "اليوم المحدد غير معتمد كيوم دوام في إعدادات المدرسة أو الفرع."})

        active_bell = self.bell_schedule
        if active_bell is None:
            bells = SchoolBellSchedule.objects.filter(
                school=self.school, academic_year=self.academic_year,
                is_active=True, is_default=True, is_archived=False,
            )
            if self.branch_id:
                active_bell = bells.filter(branch_id=self.branch_id).first() or bells.filter(branch__isnull=True).first()
            else:
                active_bell = bells.filter(branch__isnull=True).first()

        if active_bell:
            if self.period_number > active_bell.periods_per_day:
                raise ValidationError({"period_number": "رقم الحصة يتجاوز عدد الحصص في قالب الجرس."})
            if self.start_time < active_bell.day_start_time or self.end_time > active_bell.day_end_time:
                raise ValidationError({"start_time": "الحصة تقع خارج حدود اليوم الدراسي."})
            period_templates = SchedulePeriodTemplate.objects.filter(
                school=self.school, schedule=active_bell,
                period_type=SchedulePeriodTemplate.PeriodType.PERIOD,
                period_number=self.period_number, is_active=True, is_archived=False,
            )
            period_template = (
                period_templates.filter(day_of_week=self.day_of_week).first()
                or period_templates.filter(day_of_week__isnull=True).first()
            )
            if period_template and (
                self.start_time != period_template.start_time
                or self.end_time != period_template.end_time
            ):
                raise ValidationError({"start_time": "توقيت الحصة لا يطابق فترة الحصة المعتمدة في قالب الجرس."})

            non_period_templates = SchedulePeriodTemplate.objects.filter(
                school=self.school, schedule=active_bell,
                period_type__in=[
                    SchedulePeriodTemplate.PeriodType.ASSEMBLY,
                    SchedulePeriodTemplate.PeriodType.BREAK,
                    SchedulePeriodTemplate.PeriodType.PRAYER_BREAK,
                ],
                is_active=True, is_archived=False,
            ).filter(models.Q(day_of_week__isnull=True) | models.Q(day_of_week=self.day_of_week))
            for template in non_period_templates:
                if max(self.start_time, template.start_time) < min(self.end_time, template.end_time):
                    raise ValidationError({"start_time": f"توقيت الحصة يتداخل مع الفترة غير التدريسية '{template.name}'."})

        from apps.staff.models import TeacherAssignment
        assignments = TeacherAssignment.objects.filter(
            school=self.school, academic_year=self.academic_year,
            teacher=self.teacher, subject=self.subject, section=self.section,
            is_archived=False,
        )
        if self.branch_id:
            assignments = assignments.filter(models.Q(branch__isnull=True) | models.Q(branch_id=self.branch_id))
        else:
            assignments = assignments.filter(branch__isnull=True)
        assignment = assignments.first()
        if assignment is None:
            raise ValidationError({"teacher": "لا يوجد إسناد نشط لهذا المعلم والمادة والشعبة في السنة المحددة."})

        schedule_scope = ClassSchedule.objects.filter(
            school=self.school, academic_year=self.academic_year,
            day_of_week=self.day_of_week, is_archived=False,
        ).exclude(pk=self.pk)
        if self.timetable_plan_id:
            schedule_scope = schedule_scope.filter(timetable_plan_id=self.timetable_plan_id)
        else:
            schedule_scope = schedule_scope.filter(timetable_plan__isnull=True)

        conflicts = (
            ("teacher", {"teacher_id": self.teacher_id}),
            ("section", {"section_id": self.section_id}),
        )
        for field_name, lookup in conflicts:
            if schedule_scope.filter(
                **lookup, start_time__lt=self.end_time, end_time__gt=self.start_time,
            ).exists():
                raise ValidationError({field_name: "يوجد تعارض زمني مع حصة أخرى للموارد نفسها."})
        if self.classroom_id and schedule_scope.filter(
            classroom_id=self.classroom_id,
            start_time__lt=self.end_time, end_time__gt=self.start_time,
        ).exists():
            raise ValidationError({"classroom": "القاعة محجوزة لحصة أخرى في الوقت نفسه."})
        if schedule_scope.filter(teacher_id=self.teacher_id, period_number=self.period_number).exists():
            raise ValidationError({"teacher": "المعلم مرتبط بحصة أخرى في رقم الفترة نفسه."})
        if schedule_scope.filter(section_id=self.section_id, period_number=self.period_number).exists():
            raise ValidationError({"section": "الشعبة لديها حصة أخرى في رقم الفترة نفسه."})

        assignment_scope = ClassSchedule.objects.filter(
            school=self.school, academic_year=self.academic_year,
            teacher=self.teacher, subject=self.subject, section=self.section,
            is_archived=False,
        ).exclude(pk=self.pk)
        teacher_scope = ClassSchedule.objects.filter(
            school=self.school, academic_year=self.academic_year,
            teacher=self.teacher, is_archived=False,
        ).exclude(pk=self.pk)
        if self.timetable_plan_id:
            assignment_scope = assignment_scope.filter(timetable_plan_id=self.timetable_plan_id)
            teacher_scope = teacher_scope.filter(timetable_plan_id=self.timetable_plan_id)
        else:
            assignment_scope = assignment_scope.filter(timetable_plan__isnull=True)
            teacher_scope = teacher_scope.filter(timetable_plan__isnull=True)
        if assignment_scope.count() + 1 > assignment.weekly_periods:
            raise ValidationError({"period_number": "تم تجاوز النصاب الأسبوعي المسند لهذه المادة والشعبة."})
        if teacher_scope.count() + 1 > self.teacher.max_weekly_periods:
            raise ValidationError({"teacher": "تم تجاوز النصاب الأسبوعي الأقصى للمعلم."})


class DailyLessonLog(TenantOwnedModel):
    """سجل التنفيذ الفعلي للحصة الدراسية ومتابعة المنهج."""
    schedule = models.ForeignKey(
        ClassSchedule,
        verbose_name="الحصة المجدولة",
        on_delete=models.CASCADE,
        related_name="lesson_logs",
    )
    date = models.DateField("تاريخ تنفيذ الحصة")
    topic = models.CharField("عنوان موضوع الدرس المشروح", max_length=255)
    lesson_summary = models.TextField("ملخص ما تم تدريسه والإنجاز", blank=True)
    homework_assigned = models.TextField("الواجبات والتكليفات الموجهة للطلاب", blank=True)
    is_completed = models.BooleanField("تمت الحصة بنجاح", default=True)

    class Meta:
        verbose_name = "سجل درس يومي"
        verbose_name_plural = "سجلات الدروس اليومية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "schedule", "date"],
                condition=models.Q(is_archived=False),
                name="timetable_lesson_log_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.schedule} - {self.date} ({self.topic})"

    def clean(self):
        super().clean()
        schedule = self.schedule
        if schedule.school_id != self.school_id:
            raise ValidationError({"schedule": "الحصة لا تتبع المدرسة المحددة."})
        if not schedule.academic_year.starts_on <= self.date <= schedule.academic_year.ends_on:
            raise ValidationError({"date": "تاريخ تنفيذ الدرس يقع خارج السنة الدراسية."})
        python_weekday = (schedule.day_of_week - 2) % 7
        if self.date.weekday() != python_weekday:
            raise ValidationError({"date": "تاريخ تنفيذ الدرس لا يطابق يوم الحصة في الجدول الأسبوعي."})
        if schedule.timetable_plan_id:
            plan = schedule.timetable_plan
            if plan.status not in {TimetablePlan.Status.PUBLISHED, TimetablePlan.Status.RETIRED}:
                raise ValidationError({"schedule": "لا يمكن توثيق درس على نسخة جدول غير منشورة."})
            if self.date < plan.effective_from or (plan.effective_to and self.date > plan.effective_to):
                raise ValidationError({"date": "تاريخ الدرس خارج فترة سريان نسخة الجدول."})
