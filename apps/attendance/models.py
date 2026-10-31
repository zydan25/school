"""Attendance, School Calendar, Absence Management, and Attendance Scoring domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class AttendancePolicy(TenantOwnedModel):
    """سياسة وإعدادات الحضور والغياب والانصراف المعتمدة بالمدرسة."""
    class Mode(models.TextChoices):
        DAILY = "daily", "يومي فقط"
        PERIOD = "period", "حصص فقط"
        HYBRID = "hybrid", "مختلط (يومي وحصص)"

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.CASCADE,
        related_name="attendance_policies",
    )
    attendance_mode = models.CharField(
        "نمط تسجيل الحضور",
        max_length=20,
        choices=Mode.choices,
        default=Mode.DAILY,
    )
    morning_assembly_time = models.TimeField("وقت الطابور / الحضور الصباحي", default="07:30:00")
    day_end_time = models.TimeField("وقت نهاية اليوم الدراسي / الانصراف", default="13:30:00")
    grace_period_minutes = models.PositiveSmallIntegerField(
        "فترة السماح الصباحية قبل التأخر (بالدقائق)",
        default=15,
        help_text="المدة المسموحة بعد موعد الطابور قبل احتساب الطالب متأخراً",
    )
    late_to_absent_minutes = models.PositiveSmallIntegerField(
        "حد تحويل التأخر إلى غياب كامل (بالدقائق)",
        default=45,
        help_text="إذا زاد التأخر عن هذا الحد يحتسب الطالب غائباً عن اليوم",
    )
    excuse_submission_deadline_days = models.PositiveSmallIntegerField(
        "مهلة تقديم العذر بعد الغياب (أيام)",
        default=3,
        help_text="الحد الأقصى لعدد الأيام المسموح لولي الأمر بتقديم عذر لغياب سابق",
    )
    require_excuse_attachment = models.BooleanField(
        "اشتراط إرفاق مستند/تقرير طبي مع العذر",
        default=False,
    )
    auto_lock_after_days = models.PositiveSmallIntegerField(
        "الإقفال التلقائي للسجل بعد (أيام)",
        default=2,
        help_text="إقفال سجلات الحضور تلقائياً لمنع التعديل بعد مرور هذه المدة",
    )
    allow_guardian_advance_excuse = models.BooleanField("السماح لولي الأمر بطلب استئذان غياب مسبق", default=True)
    allow_guardian_post_excuse = models.BooleanField("السماح لولي الأمر بتقديم عذر لغياب سابق", default=True)
    allow_guardian_early_departure = models.BooleanField("السماح لولي الأمر بطلب انصراف مبكر", default=True)
    is_active = models.BooleanField("السياسة النشطة للعام الدراسي", default=True)
    notes = models.TextField("ملاحظات وتوجيهات السياسة", blank=True)

    class Meta:
        verbose_name = "سياسة الحضور والغياب"
        verbose_name_plural = "سياسات الحضور والغياب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year"],
                condition=Q(is_archived=False, is_active=True),
                name="attendance_policy_one_active_per_year_school",
            )
        ]

    def __str__(self) -> str:
        return f"سياسة الحضور {self.academic_year.name} ({self.get_attendance_mode_display()})"

    def clean(self):
        super().clean()
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})


class AttendanceStatusType(TenantOwnedModel):
    """أنواع وحالات الحضور والغياب المعتمدة ديناميكياً لكل مدرسة مع تصنيف قياسي."""
    class Category(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT_UNEXCUSED = "absent_unexcused", "غياب بدون عذر"
        ABSENT_EXCUSED = "absent_excused", "غياب بعذر مقبول"
        LATE = "late", "تأخر صباحي بدون عذر"
        LATE_EXCUSED = "late_excused", "تأخر بعذر مقبول"
        EARLY_DEPARTURE = "early_departure", "انصراف مبكر بدون إذن"
        AUTHORIZED_DEPARTURE = "authorized_departure", "انصراف مبكر بإذن رسمي"
        PARTIAL_ATTENDANCE = "partial_attendance", "حضور جزئي"
        DISTANCE_LEARNING = "distance_learning", "تعليم عن بعد"
        SCHOOL_ACTIVITY = "school_activity", "مهمة أو نشاط مدرسي"
        NON_SCHOOL_DAY = "non_school_day", "يوم غير دراسي / عطلة"
        CANCELLED_SESSION = "cancelled_session", "حصة أو فترة ملغاة"

    code = models.CharField("رمز الحالة", max_length=30)
    name = models.CharField("اسم الحالة", max_length=100)
    category = models.CharField("التصنيف المعياري الأساسي", max_length=30, choices=Category.choices, default=Category.PRESENT)
    color_code = models.CharField("لون التمييز (HEX)", max_length=10, default="#10b981")
    counts_as_present = models.BooleanField("تحتسب كحضور في الإحصائيات", default=True)
    counts_as_absent = models.BooleanField("تحتسب كغياب في الإحصائيات", default=False)
    is_excused = models.BooleanField("حالة مبررة / معذورة رسمياً", default=False)
    is_default = models.BooleanField("الحالة الافتراضية عند فتح السجل", default=False)
    is_active = models.BooleanField("نشطة", default=True)
    display_order = models.PositiveSmallIntegerField("ترتيب الظهور", default=1)

    class Meta:
        verbose_name = "نوع حالة حضور"
        verbose_name_plural = "أنواع حالات الحضور والغياب"
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=Q(is_archived=False),
                name="attendance_status_type_school_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_category_display()})"


class SchoolCalendar(TenantOwnedModel):
    """التقويم الأكاديمي والزمني للمدرسة أو القالب الوزاري المركزي."""
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.CASCADE,
        related_name="school_calendars",
    )
    name = models.CharField("اسم التقويم المدرسي", max_length=120)
    is_central_template = models.BooleanField("قالب تقويم وزاري / مركزي", default=False)
    source_template = models.ForeignKey(
        "self",
        verbose_name="مشتق من قالب مركزي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="derived_calendars",
    )
    version = models.PositiveIntegerField("رقم الإصدار", default=1)
    is_active = models.BooleanField("التقويم المعتمد والنشط", default=True)
    description = models.TextField("وصف التقويم", blank=True)

    class Meta:
        verbose_name = "تقويم مدرسي"
        verbose_name_plural = "التقويمات المدرسية"
        ordering = ["-academic_year__starts_on", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "name"],
                condition=Q(is_archived=False),
                name="attendance_calendar_school_year_name_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.academic_year.name}"

    def clean(self):
        super().clean()
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})


class SchoolCalendarDay(TenantOwnedModel):
    """تصنيف الأيام والتواريخ في التقويم المدرسي (أيام دراسية، إجازات، اختبارات، عطل)."""
    class DayType(models.TextChoices):
        REGULAR = "regular", "يوم دراسي عادي"
        WEEKEND = "weekend", "عطلة نهاية الأسبوع"
        PUBLIC_HOLIDAY = "public_holiday", "إجازة رسمية / وطنية"
        SCHOOL_HOLIDAY = "school_holiday", "إجازة مدرسية / فصلية"
        EMERGENCY_CLOSURE = "emergency_closure", "تعليق دراسة طارئ"
        EXAM_DAY = "exam_day", "أيام اختبارات"
        COMPENSATORY_DAY = "compensatory_day", "يوم دراسي تعويضي"
        ACTIVITY_DAY = "activity_day", "يوم نشاط / فعالية مدرسية"

    calendar = models.ForeignKey(
        SchoolCalendar,
        verbose_name="التقويم المدرسي",
        on_delete=models.CASCADE,
        related_name="days",
    )
    date = models.DateField("التاريخ", db_index=True)
    day_type = models.CharField("تصنيف اليوم", max_length=30, choices=DayType.choices, default=DayType.REGULAR)
    title = models.CharField("وصف اليوم / المناسبة", max_length=150, blank=True)
    is_school_day = models.BooleanField("يوم دوام دراسي رسمي", default=True)
    notes = models.TextField("ملاحظات إضافية", blank=True)

    class Meta:
        verbose_name = "يوم في التقويم المدرسي"
        verbose_name_plural = "أيام التقويم المدرسي"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "date"],
                condition=Q(is_archived=False),
                name="attendance_calendar_day_date_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["calendar", "date"]),
            models.Index(fields=["school", "date", "is_school_day"]),
        ]

    def __str__(self) -> str:
        return f"{self.date} ({self.get_day_type_display()}): {self.title or 'بدون عنوان'}"

    def clean(self):
        super().clean()
        if self.calendar_id and self.calendar.school_id != self.school_id:
            raise ValidationError({"calendar": "التقويم لا يتبع نفس المدرسة."})


class CalendarEvent(TenantOwnedModel):
    """فعاليات وأنشطة وبرامج تقوية ومراجعات متكررة أو مفردة."""
    class EventType(models.TextChoices):
        TUTORING = "tutoring", "حصص تقوية وبرامج علاجية"
        ACTIVITY = "activity", "نشاط لا صفي / أندية مدرسية"
        EXAM = "exam", "اختبار مجدول"
        MEETING = "meeting", "اجتماع أولياء أمور / معلمين"
        TRIP = "trip", "رحلة مدرسية"
        OTHER = "other", "أخرى"

    class RecurrenceType(models.TextChoices):
        NONE = "none", "مرة واحدة فقط"
        WEEKLY = "weekly", "أسبوعي متكرر"
        BIWEEKLY = "biweekly", "كل أسبوعين"
        MONTHLY = "monthly", "شهري"

    class TargetScope(models.TextChoices):
        ALL_SCHOOL = "all_school", "المدرسة بالكامل"
        STAGE = "stage", "مرحلة تعليمية"
        GRADE = "grade", "صف دراسي"
        SECTION = "section", "شعبة صفية محددة"

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )
    title = models.CharField("عنوان الفعالية / البرنامج", max_length=150)
    event_type = models.CharField("نوع الفعالية", max_length=30, choices=EventType.choices, default=EventType.ACTIVITY)
    recurrence_type = models.CharField("التكرار", max_length=20, choices=RecurrenceType.choices, default=RecurrenceType.NONE)
    start_date = models.DateField("تاريخ البدء")
    end_date = models.DateField("تاريخ الانتهاء (إن كان متكرراً)", null=True, blank=True)
    day_of_week = models.PositiveSmallIntegerField(
        "يوم الأسبوع (1=الأحد ... 7=السبت)",
        null=True,
        blank=True,
    )
    start_time = models.TimeField("وقت البدء", null=True, blank=True)
    end_time = models.TimeField("وقت الانتهاء", null=True, blank=True)
    target_scope = models.CharField("نطاق الفعالية", max_length=20, choices=TargetScope.choices, default=TargetScope.SECTION)
    stage = models.ForeignKey(
        "academics.EducationalStage",
        verbose_name="المرحلة المستهدفة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف المستهدف",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة المستهدفة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة المرتبطة (إن وجدت)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم / المشرف المسؤول",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    classroom = models.ForeignKey(
        "academics.Classroom",
        verbose_name="القاعة / المقر",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    is_active = models.BooleanField("نشط", default=True)
    description = models.TextField("تفاصيل الفعالية", blank=True)

    class Meta:
        verbose_name = "فعالية / برنامج مدرسي"
        verbose_name_plural = "الفعاليات والبرامج المدرسية"
        ordering = ["-start_date", "start_time"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_event_type_display()})"


class CalendarOccurrence(TenantOwnedModel):
    """جلسات وانعقادات الفعاليات الدورية والمفردة مع دعم الاستثناءات وتعديل المواعيد."""
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "مجدول"
        COMPLETED = "completed", "تم الانعقاد"
        CANCELLED = "cancelled", "ملغي"
        RESCHEDULED = "rescheduled", "مؤجل أو معدل الموعد"

    event = models.ForeignKey(
        CalendarEvent,
        verbose_name="الفعالية الأساسية",
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    date = models.DateField("تاريخ الجلسة / الانعقاد", db_index=True)
    start_time = models.TimeField("وقت البدء الفعلي", null=True, blank=True)
    end_time = models.TimeField("وقت الانتهاء الفعلي", null=True, blank=True)
    status = models.CharField("حالة الانعقاد", max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    exception_reason = models.TextField("مبرر التعديل أو الإلغاء", blank=True)

    class Meta:
        verbose_name = "جلسة فعالية"
        verbose_name_plural = "جلسات الفعاليات المجدولة"
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "date"],
                condition=Q(is_archived=False),
                name="attendance_calendar_occurrence_event_date_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.title} - {self.date} ({self.get_status_display()})"


class AttendanceRegister(TenantOwnedModel):
    """سجل الحضور الرسمي (المظلة الجامعة لجلسة الرصد مع دورة حياة الاعتماد والحماية)."""
    class SessionType(models.TextChoices):
        DAILY_MORNING = "daily_morning", "حضور يومي - صباحي"
        DAILY_EVENING = "daily_evening", "حضور يومي - مسائي"
        DAILY_FULL = "daily_full", "حضور يومي كامل"
        PERIOD = "period", "حصة دراسية مجدولة"
        EVENT = "event", "فعالية أو نشاط"

    class Status(models.TextChoices):
        OPEN = "open", "مفتوح للرصد والتعديل"
        SUBMITTED = "submitted", "تم التسليم للمراجعة"
        APPROVED = "approved", "معتمد رسمياً"
        LOCKED = "locked", "مقفل ومحمي من التعديل"

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="attendance_registers",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        verbose_name="الفصل الدراسي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attendance_registers",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية",
        on_delete=models.PROTECT,
        related_name="attendance_registers",
    )
    date = models.DateField("تاريخ الحضور", default=timezone.localdate, db_index=True)
    session_type = models.CharField("نوع الجلسة", max_length=20, choices=SessionType.choices, default=SessionType.DAILY_MORNING)
    schedule = models.ForeignKey(
        "timetable.ClassSchedule",
        verbose_name="الحصة المجدولة (إن كان نمط حصص)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_registers",
    )
    event_occurrence = models.ForeignKey(
        CalendarOccurrence,
        verbose_name="جلسة الفعالية (إن كانت فعالية)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_registers",
    )
    status = models.CharField("حالة السجل", max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="سلم بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_registers",
    )
    submitted_at = models.DateTimeField("تاريخ التسليم", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="اعتمد بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_registers",
    )
    approved_at = models.DateTimeField("تاريخ الاعتماد", null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="أقفل بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locked_registers",
    )
    locked_at = models.DateTimeField("تاريخ الإقفال", null=True, blank=True)
    notes = models.TextField("ملاحظات المشرف / المعلم", blank=True)

    class Meta:
        verbose_name = "سجل حضور معتمد"
        verbose_name_plural = "سجلات الحضور المعتمدة"
        ordering = ["-date", "-created_at"]
        constraints = [
            # Daily register uniqueness per section, date, session_type
            models.UniqueConstraint(
                fields=["school", "section", "date", "session_type"],
                condition=Q(schedule__isnull=True, event_occurrence__isnull=True, is_archived=False),
                name="attendance_register_daily_uniq",
            ),
            # Period register uniqueness per schedule and date
            models.UniqueConstraint(
                fields=["school", "schedule", "date"],
                condition=Q(schedule__isnull=False, is_archived=False),
                name="attendance_register_period_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "date", "status"]),
            models.Index(fields=["school", "section", "date"]),
        ]

    def __str__(self) -> str:
        sched_part = f" - {self.schedule.subject.name}" if self.schedule else ""
        return f"{self.section} ({self.date}) [{self.get_session_type_display()}]{sched_part}: {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة لا تتبع نفس المدرسة."})
        if self.schedule_id and self.schedule.school_id != self.school_id:
            raise ValidationError({"schedule": "الجدول المجدول لا يتبع نفس المدرسة."})
        if self.schedule_id and self.schedule.section_id != self.section_id:
            raise ValidationError({"schedule": "الحصة المجدولة لا تنتمي لنفس الشعبة المحددة للسجل."})

    @property
    def is_modifiable(self) -> bool:
        """هل السجل قابل للتعديل والإضافة؟"""
        return self.status in [self.Status.OPEN, self.Status.SUBMITTED]


class StudentAttendanceRecord(TenantOwnedModel):
    """سجل حضور أو غياب الطالب التفصيلي المربوط بسجل الحضور الرسمي."""
    register = models.ForeignKey(
        AttendanceRegister,
        verbose_name="سجل الحضور الرسمي",
        on_delete=models.CASCADE,
        related_name="student_records",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="student_attendance_records",
    )
    status_type = models.ForeignKey(
        AttendanceStatusType,
        verbose_name="نوع حالة الحضور",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="student_records",
    )
    status_category = models.CharField(
        "التصنيف المعياري الأساسي",
        max_length=30,
        choices=AttendanceStatusType.Category.choices,
        default=AttendanceStatusType.Category.PRESENT,
    )
    late_minutes = models.PositiveSmallIntegerField("دقائق التأخر (إن وجد)", default=0)
    excuse_request = models.ForeignKey(
        "AttendanceExcuseRequest",
        verbose_name="طلب العذر المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_records",
    )
    notes = models.TextField("ملاحظات المعلم / المشرف", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="رصد بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_student_attendance_records",
    )
    recorded_at = models.DateTimeField("وقت الرصد", default=timezone.now)

    class Meta:
        verbose_name = "سجل حضور طالب"
        verbose_name_plural = "سجلات حضور الطلاب التفصيلية"
        constraints = [
            models.UniqueConstraint(
                fields=["register", "student"],
                condition=Q(is_archived=False),
                name="attendance_record_register_student_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "student", "status_category"]),
            models.Index(fields=["register", "status_category"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.get_status_category_display()} ({self.register.date})"

    def clean(self):
        super().clean()
        if self.register_id and self.register.school_id != self.school_id:
            raise ValidationError({"register": "سجل الحضور لا يتبع نفس المدرسة."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.register_id and self.student_id and self.student.section_id != self.register.section_id:
            raise ValidationError({"student": "الطالب غير مقيد في نفس الشعبة التابعة لهذا السجل."})
        if self.register_id and not self.register.is_modifiable and not self._state.adding:
            # Check immutability when locked/approved
            if self.register.status == AttendanceRegister.Status.LOCKED:
                raise ValidationError("لا يمكن تعديل سجل حضور في دفتر مقفل ومحمي نهائياً.")


class AttendanceReopenRequest(TenantOwnedModel):
    """طلب رسمي معتمد لإعادة فتح سجل حضور مقفل أو معتمد."""
    class Status(models.TextChoices):
        PENDING = "pending", "قيد المراجعة"
        APPROVED = "approved", "مقبول ومفتوح"
        REJECTED = "rejected", "مرفوض"

    register = models.ForeignKey(
        AttendanceRegister,
        verbose_name="السجل المطلوب فتحه",
        on_delete=models.CASCADE,
        related_name="reopen_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="طالب إعادة الفتح",
        on_delete=models.PROTECT,
        related_name="attendance_reopen_requests",
    )
    reason = models.TextField("مبرر إعادة الفتح والتعديل")
    status = models.CharField("حالة الطلب", max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تمت المراجعة بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_reopen_requests",
    )
    reviewed_at = models.DateTimeField("تاريخ المراجعة", null=True, blank=True)
    review_notes = models.TextField("ملاحظات المعتمد", blank=True)

    class Meta:
        verbose_name = "طلب إعادة فتح سجل حضور"
        verbose_name_plural = "طلبات إعادة فتح سجلات الحضور"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"طلب فتح {self.register} ({self.get_status_display()})"


class AttendanceExcuseRequest(TenantOwnedModel):
    """طلبات واستئذانات أولياء الأمور (غياب مسبق، عذر لغياب سابق، عذر تأخر)."""
    class RequestType(models.TextChoices):
        ADVANCE_ABSENCE = "advance_absence", "استئذان غياب مسبق"
        POST_ABSENCE_EXCUSE = "post_absence_excuse", "تقديم عذر لغياب سابق"
        LATE_EXCUSE = "late_excuse", "عذر تأخر صباحي"
        UPDATE_EXCUSE = "update_excuse", "طلب مراجعة وتبرير غياب"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        SUBMITTED = "submitted", "مقدم للدراسة"
        UNDER_REVIEW = "under_review", "قيد التدقيق"
        APPROVED = "approved", "معتمد ومقبول"
        REJECTED = "rejected", "مرفوض"
        CANCELLED = "cancelled", "ملغي من ولي الأمر"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="attendance_excuse_requests",
    )
    guardian = models.ForeignKey(
        "students.Guardian",
        verbose_name="ولي الأمر المقدم للطلب",
        on_delete=models.PROTECT,
        related_name="submitted_excuse_requests",
    )
    request_type = models.CharField("نوع الطلب", max_length=30, choices=RequestType.choices, default=RequestType.POST_ABSENCE_EXCUSE)
    start_date = models.DateField("تاريخ البداية")
    end_date = models.DateField("تاريخ النهاية")
    reason = models.TextField("سبب الغياب / العذر")
    attachment = models.FileField(
        "المستند أو التقرير المرفق",
        upload_to="attendance/excuses/%Y/%m/",
        null=True,
        blank=True,
    )
    status = models.CharField("حالة الطلب", max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="راجع بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_attendance_excuses",
    )
    reviewed_at = models.DateTimeField("تاريخ المراجعة", null=True, blank=True)
    review_notes = models.TextField("ملاحظات المعتمد / سبب الرفض", blank=True)

    class Meta:
        verbose_name = "طلب عذر غياب / استئذان"
        verbose_name_plural = "طلبات أعذار الغياب والاستئذان"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "student", "status"]),
            models.Index(fields=["school", "start_date", "end_date"]),
        ]

    def __str__(self) -> str:
        return f"عذر: {self.student} ({self.start_date} إلى {self.end_date}) - {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.guardian_id and self.guardian.school_id != self.school_id:
            raise ValidationError({"guardian": "ولي الأمر لا يتبع نفس المدرسة."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "تاريخ النهاية لا يمكن أن يكون قبل تاريخ البداية."})


class EarlyDepartureRequest(TenantOwnedModel):
    """طلبات الانصراف المبكر أثناء الدوام المدرسي وتوثيق استلام الطالب عند البوابة."""
    class Status(models.TextChoices):
        PENDING = "pending", "قيد الموافقة الإدارية"
        APPROVED = "approved", "معتمد ومصرح بالانصراف"
        REJECTED = "rejected", "مرفوض"
        EXITED = "exited", "تم الخروج فعلياً من البوابة"
        CANCELLED = "cancelled", "ملغي"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="early_departure_requests",
    )
    guardian = models.ForeignKey(
        "students.Guardian",
        verbose_name="ولي الأمر",
        on_delete=models.PROTECT,
        related_name="early_departure_requests",
    )
    date = models.DateField("تاريخ الانصراف", default=timezone.localdate)
    departure_time = models.TimeField("وقت الانصراف المطلوب")
    reason = models.TextField("مبرر الانصراف المبكر")
    recipient_name = models.CharField("اسم الشخص المستلم للطالب", max_length=120)
    recipient_phone = models.CharField("رقم هاتف المستلم", max_length=25)
    recipient_relationship = models.CharField("صلة القرابة / الصفة", max_length=50)
    recipient_national_id = models.CharField("رقم هوية المستلم", max_length=50, blank=True)
    status = models.CharField("حالة الطلب", max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="اعتمد بواسطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_early_departures",
    )
    approved_at = models.DateTimeField("تاريخ ووقت الاعتماد", null=True, blank=True)
    exit_confirmed_at = models.DateTimeField("وقت الخروج الفعلي من البوابة", null=True, blank=True)
    exit_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حارس الأمن / مسؤول البوابة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exit_gate_confirmations",
    )
    exit_notes = models.TextField("ملاحظات مسؤولي البوابة والأمن", blank=True)

    class Meta:
        verbose_name = "طلب انصراف مبكر"
        verbose_name_plural = "طلبات الانصراف المبكر"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["school", "date", "status"]),
            models.Index(fields=["school", "student", "date"]),
        ]

    def __str__(self) -> str:
        return f"انصراف مبكر: {self.student} ({self.date} {self.departure_time}) - {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.guardian_id and self.guardian.school_id != self.school_id:
            raise ValidationError({"guardian": "ولي الأمر لا يتبع نفس المدرسة."})


class AttendanceScoringPolicy(TenantOwnedModel):
    """سياسة احتساب درجات المواظبة وربطها بسجل الدرجات."""
    class CalculationMode(models.TextChoices):
        AUTO = "auto", "احتساب آلي بالكامل"
        TEACHER = "teacher", "يدوي من المعلم"
        HYBRID = "hybrid", "مقترح آلياً مع اعتماد المعلم"

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.CASCADE,
        related_name="attendance_scoring_policies",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية (فارغ = عام لكافة المواد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_scoring_policies",
    )
    total_attendance_score = models.DecimalField("الدرجة الكلية المخصصة للمواظبة", max_digits=5, decimal_places=2, default=Decimal("10.00"))
    calculation_mode = models.CharField(
        "آلية الاحتساب",
        max_length=20,
        choices=CalculationMode.choices,
        default=CalculationMode.AUTO,
    )
    unexcused_absence_deduction = models.DecimalField("حسم الغياب بدون عذر (لكل يوم/حصة)", max_digits=5, decimal_places=2, default=Decimal("1.00"))
    unexcused_late_deduction = models.DecimalField("حسم التأخر بدون عذر (لكل مرة)", max_digits=5, decimal_places=2, default=Decimal("0.25"))
    excused_absence_deduction = models.DecimalField("حسم الغياب بعذر مقبول", max_digits=5, decimal_places=2, default=Decimal("0.00"))
    min_score = models.DecimalField("الحد الأدنى لدرجة المواظبة (لا ينزل عنها)", max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField("نشطة", default=True)
    notes = models.TextField("ملاحظات وتوجيهات الحسم", blank=True)

    class Meta:
        verbose_name = "سياسة درجات المواظبة"
        verbose_name_plural = "سياسات درجات المواظبة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "subject"],
                condition=Q(is_archived=False, is_active=True),
                name="attendance_scoring_policy_uniq",
            )
        ]

    def __str__(self) -> str:
        subj_str = f" - {self.subject.name}" if self.subject else " (عام لكافة المواد)"
        return f"سياسة درجات {self.academic_year.name}{subj_str}: {self.total_attendance_score} درجة"


class AttendanceScoreEntry(TenantOwnedModel):
    """رصد واحتساب درجات المواظبة لكل طالب في الفصل الدراسي وتكاملها مع GradeBook."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="attendance_scores",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        verbose_name="الفصل الدراسي",
        on_delete=models.CASCADE,
        related_name="student_attendance_scores",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة (إن كانت محددة)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_attendance_scores",
    )
    scoring_policy = models.ForeignKey(
        AttendanceScoringPolicy,
        verbose_name="سياسة درجات المواظبة المطبقة",
        on_delete=models.PROTECT,
        related_name="score_entries",
    )
    raw_score = models.DecimalField("الدرجة الأساسية قبل الحسم", max_digits=6, decimal_places=2, default=Decimal("10.00"))
    unexcused_absence_count = models.PositiveIntegerField("عدد أيام/حصص الغياب بدون عذر", default=0)
    excused_absence_count = models.PositiveIntegerField("عدد أيام/حصص الغياب بعذر", default=0)
    late_count = models.PositiveIntegerField("مرات التأخر", default=0)
    deduction_total = models.DecimalField("إجمالي درجات الحسم", max_digits=6, decimal_places=2, default=Decimal("0.00"))
    final_score = models.DecimalField("الدرجة النهائية للمواظبة", max_digits=6, decimal_places=2, default=Decimal("10.00"))
    calculated_at = models.DateTimeField("تاريخ آخر احتساب", default=timezone.now)
    is_synced_to_gradebook = models.BooleanField("مرحلة لسجل الدرجات الرسمي", default=False)
    gradebook_entry = models.ForeignKey(
        "assessments.GradeBook",
        verbose_name="سجل الدرجات المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_score_source",
    )
    notes = models.TextField("ملاحظات الرصد", blank=True)

    class Meta:
        verbose_name = "درجة مواظبة طالب"
        verbose_name_plural = "سجل درجات المواظبة للطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "academic_term", "subject"],
                condition=Q(is_archived=False),
                name="attendance_score_entry_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "academic_term", "student"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - مواظبة: {self.final_score}/{self.raw_score} ({self.academic_term.name})"


class AttendanceAuditLog(TenantOwnedModel):
    """سجل رقابي غير قابل للتعديل لكافة حركات وإجراءات الحضور والغياب."""
    class Action(models.TextChoices):
        REGISTER_CREATED = "register_created", "إنشاء سجل حضور"
        REGISTER_SUBMITTED = "register_submitted", "تسليم السجل"
        REGISTER_APPROVED = "register_approved", "اعتماد السجل"
        REGISTER_LOCKED = "register_locked", "إقفال السجل"
        RECORD_UPDATED = "record_updated", "تعديل حالة حضور طالب"
        REOPEN_REQUESTED = "reopen_requested", "طلب فتح سجل مقفل"
        REOPEN_APPROVED = "reopen_approved", "الموافقة على فتح سجل مقفل"
        EXCUSE_REVIEWED = "excuse_reviewed", "مراجعة عذر غياب"
        EARLY_EXIT_CONFIRMED = "early_exit_confirmed", "تأكيد خروج طالب من البوابة"

    register = models.ForeignKey(
        AttendanceRegister,
        verbose_name="سجل الحضور",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    student_record = models.ForeignKey(
        StudentAttendanceRecord,
        verbose_name="سجل الطالب",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField("نوع الإجراء", max_length=40, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="قام بالإجراء",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_audit_logs",
    )
    timestamp = models.DateTimeField("تاريخ ووقت الإجراء", default=timezone.now)
    old_value = models.JSONField("القيمة السابقة", default=dict, blank=True)
    new_value = models.JSONField("القيمة الجديدة", default=dict, blank=True)
    reason = models.TextField("السبب / التبرير", blank=True)
    ip_address = models.GenericIPAddressField("عنوان IP", null=True, blank=True)

    class Meta:
        verbose_name = "سجل تدقيق حضور"
        verbose_name_plural = "سجلات تدقيق الحضور والغياب"
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# Backward compatibility models
class DailyAttendance(TenantOwnedModel):
    """سجل الحضور والغياب اليومي للطالب على مستوى المدرسة (متوافق مع الإصدارات السابقة)."""
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
    # Linked new architecture
    register = models.ForeignKey(
        AttendanceRegister,
        verbose_name="سجل الحضور الرسمي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="daily_attendances",
    )
    detailed_record = models.ForeignKey(
        StudentAttendanceRecord,
        verbose_name="السجل المفصل",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="legacy_daily_attendance",
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
    """سجل حضور وغياب الطالب في حصة دراسية مجدولة محددة (متوافق مع الإصدارات السابقة)."""
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
    # Linked new architecture
    register = models.ForeignKey(
        AttendanceRegister,
        verbose_name="سجل الحضور الرسمي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="period_attendances",
    )
    detailed_record = models.ForeignKey(
        StudentAttendanceRecord,
        verbose_name="السجل المفصل",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="legacy_period_attendance",
    )

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
