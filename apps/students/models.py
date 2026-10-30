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
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع نفس المدرسة."})
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
    children = models.ManyToManyField(
        Student,
        through="StudentGuardianRelation",
        related_name="linked_guardians",
        verbose_name="الأبناء والطلاب المكفولون",
        blank=True,
    )

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

    def get_students(self):
        """إرجاع كشف الأبناء الفعليين والطلاب المرتبطين بولي الأمر بأمان تام."""
        return Student.objects.filter(guardians__guardian=self, is_archived=False)


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


# -----------------------------------------------------------------------------
# Disciplinary Incidents, Administrative Summons, and Complaints Workflow
# -----------------------------------------------------------------------------

class StudentIncidentReport(TenantOwnedModel):
    """بلاغات المعلمين السلوكية وإخطارات أولياء الأمور."""
    class IncidentType(models.TextChoices):
        ACADEMIC_NEGLECT = "academic_neglect", "إهمال دراسي / عدم حل واجبات"
        BEHAVIORAL = "behavioral", "مخالفة سلوكية أو انضباطية"
        TARDINESS = "tardiness", "تأخر صباحي متكرر"
        ABSENCE = "absence", "غياب بدون عذر"
        COMMENDATION = "commendation", "خطاب شكر وتقدير وتميز"

    class Severity(models.TextChoices):
        LOW = "low", "بسيط (تنبيه شفوي)"
        MEDIUM = "medium", "متوسط (إشعار رسمي لولي الأمر)"
        HIGH = "high", "جسيم (إحالة لإدارة المدرسة والإرشاد)"

    student = models.ForeignKey(
        Student,
        verbose_name="الطالب المعني",
        on_delete=models.CASCADE,
        related_name="incident_reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="محرر البلاغ (المعلم / المشرف)",
        on_delete=models.PROTECT,
        related_name="filed_incidents",
    )
    date = models.DateField("تاريخ الواقعة", default=timezone.localdate)
    incident_type = models.CharField("نوع البلاغ", max_length=30, choices=IncidentType.choices, default=IncidentType.BEHAVIORAL)
    severity = models.CharField("درجة الأهمية", max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    title = models.CharField("عنوان البلاغ / الواقعة", max_length=200)
    details = models.TextField("تفاصيل الواقعة وملاحظات المعلم")
    action_taken = models.TextField("الإجراء المتخذ والتوصيات", blank=True)
    parent_notified = models.BooleanField("تم إشعار ولي الأمر (رسالة / اتصال)", default=False)
    parent_seen_at = models.DateTimeField("تاريخ اطلاع ولي الأمر عبر البوابة", null=True, blank=True)
    is_resolved = models.BooleanField("تم تسوية البلاغ ومعالجته", default=False)

    class Meta:
        verbose_name = "بلاغ سلوكي / تقرير معلم"
        verbose_name_plural = "سجل البلاغات والتقارير السلوكية"

    def __str__(self) -> str:
        return f"{self.student}: {self.title} ({self.get_incident_type_display()})"


class AdministrativeSummon(TenantOwnedModel):
    """استدعاءات رسمية من إدارة المدرسة (لولي الأمر، الطالب، أو المعلم)."""
    class TargetType(models.TextChoices):
        GUARDIAN = "guardian", "استدعاء ولي أمر طالب"
        STUDENT = "student", "استدعاء طالب"
        TEACHER = "teacher", "استدعاء معلم / موظف"

    summon_type = models.CharField("فئة المستدعى", max_length=20, choices=TargetType.choices, default=TargetType.GUARDIAN)
    student = models.ForeignKey(
        Student,
        verbose_name="الطالب المرتبط (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="summons",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="الشخص المستدعى",
        on_delete=models.PROTECT,
        related_name="received_summons",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المسؤول المصدِر للاستدعاء",
        on_delete=models.PROTECT,
        related_name="issued_summons",
    )
    reason = models.TextField("سبب وموضوع الاستدعاء الرسمي")
    appointment_date = models.DateTimeField("موعد وتوقيت الحضور للمدرسة")
    location = models.CharField("الموقع المكتبي (مكتب المدير، الإرشاد، الكنترول)", max_length=150, default="مكتب إدارة المدرسة")
    is_attended = models.BooleanField("تم الحضور والمقابلة", default=False)
    attended_at = models.DateTimeField("وقت الحضور الفعلي", null=True, blank=True)
    session_minutes = models.TextField("محضر وقائع الجلسة والتعهدات والنتائج", blank=True)

    class Meta:
        verbose_name = "استدعاء إداري رسمي"
        verbose_name_plural = "سجل الاستدعاءات الإدارية"

    def __str__(self) -> str:
        return f"استدعاء {self.get_summon_type_display()}: {self.target_user} ({self.appointment_date.strftime('%Y-%m-%d %H:%M')})"


class SchoolComplaint(TenantOwnedModel):
    """صندوق الشكاوى والمقترحات للطلاب وأولياء الأمور."""
    class Category(models.TextChoices):
        ACADEMIC = "academic", "شكوى أكاديمية أو تعليمية"
        TRANSPORTATION = "transportation", "خدمات النقل والحافلات"
        FINANCIAL = "financial", "الرسوم والمطالبات المالية"
        ADMINISTRATIVE = "administrative", "تعامل إداري أو تنظيمي"
        FACILITIES = "facilities", "المرافق والنظافة والتجهيزات"
        OTHER = "other", "أخرى"

    class Status(models.TextChoices):
        NEW = "new", "جديدة"
        IN_REVIEW = "in_review", "قيد المراجعة والبحث"
        RESOLVED = "resolved", "تمت المعالجة والحل"
        CLOSED = "closed", "مغلقة"

    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="مقدم الشكوى",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_complaints",
    )
    category = models.CharField("تصنيف الشكوى", max_length=30, choices=Category.choices, default=Category.ACADEMIC)
    subject = models.CharField("موضوع الشكوى", max_length=200)
    details = models.TextField("تفاصيل الشكوى أو المقترح")
    status = models.CharField("حالة الشكوى", max_length=20, choices=Status.choices, default=Status.NEW)
    resolution_notes = models.TextField("رد الإدارة وإجراءات المعالجة", blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المسؤول المعالج",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_complaints",
    )
    resolved_at = models.DateTimeField("تاريخ وتوقيت الحل", null=True, blank=True)

    class Meta:
        verbose_name = "شكوى / مقترح"
        verbose_name_plural = "صندوق الشكاوى والمقترحات"

    def __str__(self) -> str:
        return f"[{self.get_category_display()}] {self.subject} - {self.get_status_display()}"
