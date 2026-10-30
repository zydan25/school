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
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم المحدد لا يتبع نفس المدرسة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة المحددة لا تتبع نفس المدرسة."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة المحددة لا تتبع نفس المدرسة."})


class StaffMember(TenantOwnedModel):
    """
    سجل الموظفين والكادر الإداري والإشرافي للمدرسة
    (مشرفو الأدوار والأقسام، مسؤولو الكنترول، أمناء المستودعات، المحاسبون، أمناء الصناديق، الإرشاد).
    """
    class StaffRole(models.TextChoices):
        SUPERVISOR = "supervisor", "مشرف أدوار / أقسام"
        CONTROL_OFFICER = "control_officer", "مسؤول كنترول واختبارات"
        STORE_KEEPER = "store_keeper", "أمين مخزن ومستودع"
        ACCOUNTANT = "accountant", "محاسب مالي"
        CASHIER = "cashier", "أمين صندوق"
        LIBRARIAN = "librarian", "أمين مكتبة"
        SOCIAL_WORKER = "social_worker", "مرشد طلابي / أخصائي اجتماعي"
        SECRETARY = "secretary", "سكرتارية وشؤون طلاب"
        NURSE = "nurse", "ممرض / مسؤول صحي"
        BUS_SUPERVISOR = "bus_supervisor", "مشرف حافلة"
        OTHER = "other", "إداري / أخرى"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب تسجيل الدخول",
        on_delete=models.PROTECT,
        related_name="staff_profiles",
        db_index=True,
    )
    employee_number = models.CharField("الرقم الوظيفي", max_length=50, blank=True)
    job_title = models.CharField("المسمى الوظيفي الفعلي", max_length=150)
    role = models.CharField("التصنيف الإداري", max_length=30, choices=StaffRole.choices, default=StaffRole.OTHER)
    assigned_floor_wing = models.CharField("الدور / القسم المسؤول عنه (مثل: الدور الأول)", max_length=150, blank=True)
    hire_date = models.DateField("تاريخ التعيين", default=timezone.now)
    is_active = models.BooleanField("على رأس العمل", default=True)

    class Meta:
        verbose_name = "موظف / إداري"
        verbose_name_plural = "الكادر الإداري والإشرافي"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "user", "role"],
                condition=models.Q(is_archived=False),
                name="staff_member_school_user_role_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.phone} ({self.get_role_display()} - {self.job_title})"


class Department(TenantOwnedModel):
    """الأقسام والإدارات التنظيمية في هيكل المدرسة (شؤون الطلاب، الكنترول، المالية، الإشراف التربوي...)."""
    code = models.CharField("رمز القسم / الإدارة", max_length=50, db_index=True)
    name = models.CharField("اسم القسم / الإدارة", max_length=150)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="مدير / رئيس القسم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
    )
    description = models.TextField("وصف واختصاصات القسم", blank=True)

    class Meta:
        verbose_name = "قسم / إدارة"
        verbose_name_plural = "الهيكل التنظيمي والأقسام"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="staff_department_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.code}]"


class WorkShift(TenantOwnedModel):
    """ورديات وساعات الدوام الرسمي للكادر والموظفين."""
    name = models.CharField("اسم الوردية (مثل: الدوام الصباحي الأساسي)", max_length=100)
    start_time = models.TimeField("وقت بدء الدوام")
    end_time = models.TimeField("وقت انتهاء الدوام")
    grace_period_minutes = models.PositiveSmallIntegerField("فترة السماح قبل احتساب التأخير (دقائق)", default=15)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "وردية دوام"
        verbose_name_plural = "ورديات وساعات الدوام"

    def __str__(self) -> str:
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class LeaveType(TenantOwnedModel):
    """أنواع الإجازات السنوية والرسمية (اعتيادية، مرضية، طارئة، أمومة، بدون راتب)."""
    code = models.CharField("رمز الإجازة", max_length=30)
    name = models.CharField("مسمى الإجازة", max_length=100)
    days_allowed = models.PositiveSmallIntegerField("الرصيد المسموح به سنوياً (أيام)", default=30)
    is_paid = models.BooleanField("إجازة مدفوعة الراتب", default=True)

    class Meta:
        verbose_name = "نوع إجازة"
        verbose_name_plural = "أنواع الإجازات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="staff_leave_type_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.days_allowed} يوم)"


class LeaveRequest(TenantOwnedModel):
    """طلبات الإجازات للموظفين والمعلمين وسير دورة اعتمادها."""
    class Status(models.TextChoices):
        PENDING = "pending", "قيد المراجعة"
        APPROVED = "approved", "معتمدة"
        REJECTED = "rejected", "مرفوضة"

    teacher = models.ForeignKey(
        Teacher,
        verbose_name="المعلم مقدم الطلب",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    staff_member = models.ForeignKey(
        StaffMember,
        verbose_name="الموظف الإداري مقدم الطلب",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.ForeignKey(
        LeaveType,
        verbose_name="نوع الإجازة",
        on_delete=models.PROTECT,
        related_name="requests",
    )
    start_date = models.DateField("تاريخ بدء الإجازة")
    end_date = models.DateField("تاريخ نهاية الإجازة")
    reason = models.TextField("مبررات وسبب الإجازة")
    status = models.CharField("حالة الطلب", max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_leaves",
    )
    approved_at = models.DateTimeField("تاريخ الاعتماد", null=True, blank=True)

    class Meta:
        verbose_name = "طلب إجازة"
        verbose_name_plural = "طلبات إجازات الموظفين"

    def __str__(self) -> str:
        emp = self.teacher or self.staff_member or "موظف"
        return f"إجازة {emp} ({self.start_date} إلى {self.end_date}): {self.get_status_display()}"

    def clean(self):
        super().clean()
        if bool(self.teacher_id) == bool(self.staff_member_id):
            raise ValidationError("يجب تحديد مقدم الطلب إما معلماً أو موظفاً إدارياً.")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("تاريخ بدء الإجازة لا يمكن أن يكون بعد تاريخ نهايتها.")


class StaffAttendance(TenantOwnedModel):
    """سجل الحضور والانصراف اليومي للموظفين والمعلمين (التكامل مع البصمة وساعات الدوام)."""
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر في الموعد"
        LATE = "late", "حاضر بتأخر"
        EXCUSED = "excused", "غياب بعذر معتمد"
        UNEXCUSED = "unexcused", "غياب بدون عذر"

    teacher = models.ForeignKey(
        Teacher,
        verbose_name="المعلم",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    staff_member = models.ForeignKey(
        StaffMember,
        verbose_name="الموظف الإداري",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField("تاريخ يوم الدوام", default=timezone.localdate)
    time_in = models.TimeField("وقت الحضور الفعلي", null=True, blank=True)
    time_out = models.TimeField("وقت الانصراف الفعلي", null=True, blank=True)
    status = models.CharField("حالة الدوام", max_length=20, choices=Status.choices, default=Status.PRESENT)
    delay_minutes = models.PositiveSmallIntegerField("دقائق التأخر إن وجدت", default=0)
    notes = models.TextField("ملاحظات الدوام", blank=True)

    class Meta:
        verbose_name = "سجل دوام موظف"
        verbose_name_plural = "حضور وانصراف الكادر والموظفين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "teacher", "date"],
                condition=models.Q(is_archived=False, teacher__isnull=False),
                name="staff_teacher_attendance_date_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "staff_member", "date"],
                condition=models.Q(is_archived=False, staff_member__isnull=False),
                name="staff_member_attendance_date_uniq",
            ),
        ]

    def __str__(self) -> str:
        emp = self.teacher or self.staff_member or "موظف"
        return f"دوام {emp} في {self.date}: {self.get_status_display()}"
