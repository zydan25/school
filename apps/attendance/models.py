"""Attendance domain models."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class DailyAttendance(TenantOwnedModel):
    """سجل الحضور والغياب اليومي للطالب على مستوى المدرسة."""
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT_UNEXCUSED = "absent_unexcused", "غياب بدون عذر"
        ABSENT_EXCUSED = "absent_excused", "غياب بعذر مقبول"
        LATE = "late", "تأخر صباحي"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="daily_attendances",
    )
    date = models.DateField("تاريخ اليوم الدراسي", default=timezone.localdate)
    status = models.CharField("حالة الحضور", max_length=20, choices=Status.choices, default=Status.PRESENT)
    late_minutes = models.PositiveSmallIntegerField("دقائق التأخر (إن وجد)", default=0)
    excuse_reason = models.TextField("سبب وتفاصيل العذر المقبول", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="سجله الموظف",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_daily_attendances",
    )

    class Meta:
        verbose_name = "سجل حضور يومي"
        verbose_name_plural = "سجلات الحضور اليومي"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "date"],
                condition=models.Q(is_archived=False),
                name="attendance_daily_student_date_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "date", "status"]),
            models.Index(fields=["school", "student", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.date}: {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})


class PeriodAttendance(TenantOwnedModel):
    """سجل حضور وغياب الطالب في حصة دراسية مجدولة محددة."""
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر في الحصة"
        ABSENT = "absent", "غائب عن الحصة"
        LATE = "late", "متأخر عن الحصة"

    schedule = models.ForeignKey(
        "timetable.ClassSchedule",
        verbose_name="الحصة الدراسية المجدولة",
        on_delete=models.CASCADE,
        related_name="period_attendances",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="period_attendances",
    )
    date = models.DateField("تاريخ الحصة", default=timezone.localdate)
    status = models.CharField("حالة الحضور", max_length=20, choices=Status.choices, default=Status.PRESENT)
    notes = models.CharField("ملاحظات المعلم على الحصة", max_length=255, blank=True)

    class Meta:
        verbose_name = "سجل حضور حصة"
        verbose_name_plural = "سجلات حضور الحصص"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "schedule", "student", "date"],
                condition=models.Q(is_archived=False),
                name="attendance_period_student_date_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "date", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.schedule.subject.name} ({self.date}): {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.schedule_id and self.schedule.school_id != self.school_id:
            raise ValidationError({"schedule": "الحصة المجدولة لا تتبع نفس المدرسة."})
        if self.student_id and self.schedule_id and self.student.section_id != self.schedule.section_id:
            raise ValidationError({"student": "الطالب غير مسجل في نفس الشعبة الدراسية لهذه الحصة المجدولة."})
