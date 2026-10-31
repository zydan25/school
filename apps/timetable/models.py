"""Timetable, Bell Schedule, and scheduled lesson models."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import models
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
            models.UniqueConstraint(
                fields=["school", "academic_year", "name"],
                condition=models.Q(is_archived=False),
                name="timetable_bellsched_school_name_uniq",
            )
        ]

    def __str__(self) -> str:
        default_tag = " (افتراضي)" if self.is_default else ""
        return f"{self.name} - {self.school.name}{default_tag}"

    def clean(self):
        super().clean()
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})

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
        if self.is_default and self.school_id:
            SchoolBellSchedule.objects.filter(
                school_id=self.school_id,
                academic_year_id=self.academic_year_id,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


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
            # منع تعارض الشعبة في نفس اليوم والحصة
            models.UniqueConstraint(
                fields=["school", "academic_year", "section", "day_of_week", "period_number"],
                condition=models.Q(is_archived=False),
                name="timetable_schedule_section_period_uniq",
            ),
            # منع تعارض المعلم في حصتين متزامنتين بنفس رقم الحصة
            models.UniqueConstraint(
                fields=["school", "academic_year", "teacher", "day_of_week", "period_number"],
                condition=models.Q(is_archived=False),
                name="timetable_schedule_teacher_period_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "section", "day_of_week"]),
            models.Index(fields=["school", "teacher", "day_of_week"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_day_of_week_display()} [حصة {self.period_number}]: {self.subject.name} - {self.section}"

    def clean(self):
        super().clean()
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "وقت نهاية الحصة يجب أن يكون بعد وقت البداية."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة المحددة لا تتبع نفس المدرسة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة المحددة لا تتبع نفس المدرسة."})
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم المحدد لا يتبع نفس المدرسة."})
        if self.classroom_id and self.classroom.school_id != self.school_id:
            raise ValidationError({"classroom": "القاعة المحددة لا تتبع نفس المدرسة."})

        # 1. منع تعارض القاعة في نفس الوقت
        if self.classroom_id and self.start_time and self.end_time:
            classroom_conflict = ClassSchedule.objects.filter(
                school=self.school,
                academic_year=self.academic_year,
                classroom=self.classroom,
                day_of_week=self.day_of_week,
                is_archived=False,
            ).exclude(pk=self.pk).filter(
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).first()
            if classroom_conflict:
                raise ValidationError({"classroom": f"القاعة المحددة محجوزة لحصة أخرى ({classroom_conflict.subject.name} - شعبة {classroom_conflict.section.name}) في نفس الوقت ({classroom_conflict.start_time.strftime('%H:%M')} - {classroom_conflict.end_time.strftime('%H:%M')})."})

        # 2. منع تعارض المعلم الزمني الدقيق (تداخل الأوقات)
        if self.teacher_id and self.start_time and self.end_time:
            teacher_conflict = ClassSchedule.objects.filter(
                school=self.school,
                academic_year=self.academic_year,
                teacher=self.teacher,
                day_of_week=self.day_of_week,
                is_archived=False,
            ).exclude(pk=self.pk).filter(
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).first()
            if teacher_conflict:
                raise ValidationError({"teacher": f"تعارض زمني: المعلم مسند له حصة أخرى ({teacher_conflict.subject.name} - شعبة {teacher_conflict.section.name}) في نفس الوقت ({teacher_conflict.start_time.strftime('%H:%M')} - {teacher_conflict.end_time.strftime('%H:%M')})."})

        # 3. منع تعارض الشعبة الزمني الدقيق (تداخل الأوقات)
        if self.section_id and self.start_time and self.end_time:
            section_conflict = ClassSchedule.objects.filter(
                school=self.school,
                academic_year=self.academic_year,
                section=self.section,
                day_of_week=self.day_of_week,
                is_archived=False,
            ).exclude(pk=self.pk).filter(
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).first()
            if section_conflict:
                raise ValidationError({"section": f"تعارض زمني: الشعبة مجدول لها حصة أخرى ({section_conflict.subject.name}) في نفس الوقت ({section_conflict.start_time.strftime('%H:%M')} - {section_conflict.end_time.strftime('%H:%M')})."})

        # 4. منع جدولة حصة في وقت الطابور الصباحي أو أوقات الفسحة والاستراحة المعتمدة
        active_bell = self.bell_schedule or SchoolBellSchedule.objects.filter(
            school=self.school,
            academic_year=self.academic_year,
            is_active=True,
            is_default=True,
            is_archived=False,
        ).first()

        if active_bell and self.start_time and self.end_time:
            non_period_templates = SchedulePeriodTemplate.objects.filter(
                school=self.school,
                schedule=active_bell,
                period_type__in=[
                    SchedulePeriodTemplate.PeriodType.ASSEMBLY,
                    SchedulePeriodTemplate.PeriodType.BREAK,
                    SchedulePeriodTemplate.PeriodType.PRAYER_BREAK,
                ],
                is_active=True,
                is_archived=False,
            ).filter(
                models.Q(day_of_week__isnull=True) | models.Q(day_of_week=self.day_of_week)
            )

            for b_tpl in non_period_templates:
                if max(self.start_time, b_tpl.start_time) < min(self.end_time, b_tpl.end_time):
                    raise ValidationError(
                        f"لا يمكن جدولة الحصة في هذا التوقيت: تتعارض الحصة مع وقت '{b_tpl.name}' "
                        f"({b_tpl.start_time.strftime('%H:%M')} - {b_tpl.end_time.strftime('%H:%M')}). "
                        f"يرجى الالتزام بمواعيد الفسح والاستراحات والطابور المعتمدة."
                    )


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
