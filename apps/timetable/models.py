"""Timetable and scheduled lesson models."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TenantOwnedModel


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
            # منع تعارض المعلم في حصتين متزامنتين
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
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة المحددة لا تتبع نفس المدرسة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة المحددة لا تتبع نفس المدرسة."})
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم المحدد لا يتبع نفس المدرسة."})
        if self.classroom_id and self.classroom.school_id != self.school_id:
            raise ValidationError({"classroom": "القاعة المحددة لا تتبع نفس المدرسة."})


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
