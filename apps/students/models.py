"""Student and guardian domain models."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
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
    credit_balance = models.DecimalField("الرصيد الدائن المتبقي (دفعات زائدة)", max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "طالب"
        verbose_name_plural = "الطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student_id_number"],
                condition=models.Q(is_archived=False),
                name="students_student_school_id_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "user"],
                condition=models.Q(user__isnull=False, is_archived=False),
                name="students_student_school_user_uniq",
            ),
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
        if self.section_id and self.academic_year_id and self.section.academic_year_id != self.academic_year_id:
            raise ValidationError({"section": "الشعبة الصفية لا تنتمي إلى السنة الدراسية المحددة للطالب."})

    def save(self, *args, **kwargs):
        # The student record and its initial annual enrollment are one operation.
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.academic_year_id and self.grade_level_id and self.section_id:
                StudentEnrollment.objects.get_or_create(
                    school=self.school,
                    student=self,
                    academic_year=self.academic_year,
                    defaults={
                        "grade_level": self.grade_level,
                        "section": self.section,
                        "enrollment_date": self.enrollment_date,
                        "status": StudentEnrollment.Status.ENROLLED,
                    },
                )


class StudentMovement(TenantOwnedModel):
    """Append-only lifecycle history for admissions and student status/placement changes."""

    class MovementType(models.TextChoices):
        ADMITTED = "admitted", "قبول وتسجيل"
        PROMOTED = "promoted", "ترفيع"
        RETAINED = "retained", "إعادة قيد"
        TRANSFERRED = "transferred", "نقل داخلي"
        GRADUATED = "graduated", "تخرج"
        WITHDRAWN = "withdrawn", "انسحاب"

    student = models.ForeignKey(
        Student,
        verbose_name="الطالب",
        on_delete=models.PROTECT,
        related_name="movements",
    )
    movement_type = models.CharField(
        "نوع الحركة", max_length=20, choices=MovementType.choices,
    )
    previous_academic_year = models.ForeignKey(
        "academics.AcademicYear", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    previous_grade_level = models.ForeignKey(
        "academics.GradeLevel", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    previous_section = models.ForeignKey(
        "academics.Section", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    next_academic_year = models.ForeignKey(
        "academics.AcademicYear", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    next_grade_level = models.ForeignKey(
        "academics.GradeLevel", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    next_section = models.ForeignKey(
        "academics.Section", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    effective_date = models.DateField("تاريخ سريان الحركة", default=timezone.localdate)
    reason = models.TextField("سبب الحركة وملاحظاتها", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recorded_student_movements",
    )

    class Meta:
        verbose_name = "حركة طالب"
        verbose_name_plural = "سجل حركات الطلاب"
        ordering = ["-effective_date", "-created_at"]
        indexes = [
            models.Index(
                fields=["school", "student", "effective_date"],
                name="studmov_school_student_idx",
            ),
            models.Index(
                fields=["school", "movement_type", "effective_date"],
                name="studmov_school_type_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة المحددة."})
        for field_name in (
            "previous_academic_year", "previous_grade_level", "previous_section",
            "next_academic_year", "next_grade_level", "next_section",
        ):
            related = getattr(self, field_name, None)
            if related is not None and related.school_id != self.school_id:
                raise ValidationError({field_name: "العنصر المرتبط لا يتبع المدرسة المحددة."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("سجل حركة الطالب لا يقبل التعديل؛ أضف حركة تصحيحية جديدة.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("سجل حركة الطالب تاريخي ولا يمكن حذفه.")


class StudentEnrollment(TenantOwnedModel):
    """السجل الأكاديمي وتاريخ قيد الطالب لكل عام دراسي (الترفيع، الإعادة، النقل، التخرج)."""
    class Status(models.TextChoices):
        ENROLLED = "enrolled", "مقيد ومنتظم"
        PROMOTED = "promoted", "مرفع للصف الأعلى"
        RETAINED = "retained", "معيد للسنة الدراسية"
        TRANSFERRED = "transferred", "منقول لمدرسة أخرى"
        WITHDRAWN = "withdrawn", "منسحب"
        GRADUATED = "graduated", "متخرج"

    class FinalResult(models.TextChoices):
        PENDING = "pending", "قيد الدراسة"
        PASSED = "passed", "ناجح"
        FAILED = "failed", "راسب"

    student = models.ForeignKey(
        Student,
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="enrollment_history",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي",
        on_delete=models.PROTECT,
        related_name="student_enrollments",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية",
        on_delete=models.PROTECT,
        related_name="student_enrollments",
    )
    enrollment_date = models.DateField("تاريخ القيد", default=timezone.now)
    status = models.CharField("حالة القيد في هذا العام", max_length=20, choices=Status.choices, default=Status.ENROLLED)
    final_result = models.CharField("النتيجة الختامية للعام", max_length=20, choices=FinalResult.choices, default=FinalResult.PENDING)
    notes = models.TextField("ملاحظات وسجل الحركة الأكاديمية", blank=True)

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "ملف الطالب لا يتبع المدرسة المحددة."})
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة المحددة."})
        if self.grade_level_id and self.grade_level.school_id != self.school_id:
            raise ValidationError({"grade_level": "الصف الدراسي لا يتبع المدرسة المحددة."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة لا تتبع المدرسة المحددة."})
        if self.section_id and self.grade_level_id and self.section.grade_id != self.grade_level_id:
            raise ValidationError({"section": "الشعبة لا تنتمي إلى الصف المحدد في سجل القيد."})
        if self.section_id and self.academic_year_id and self.section.academic_year_id != self.academic_year_id:
            raise ValidationError({"section": "الشعبة لا تنتمي إلى السنة الدراسية المحددة في سجل القيد."})

    class Meta:
        verbose_name = "سجل قيد سنوي لطالب"
        verbose_name_plural = "السجل الأكاديمي وتاريخ قيد الطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "academic_year"],
                condition=models.Q(is_archived=False),
                name="students_enrollment_student_year_uniq",
            )
        ]
        ordering = ["-academic_year__starts_on"]

    def __str__(self) -> str:
        return f"{self.student} - {self.academic_year.name}: {self.grade_level.name} ({self.get_status_display()})"


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


def validate_student_document_file(value):
    """Accept common document/image formats and cap each file at 10 MiB."""
    if value.size > 10 * 1024 * 1024:
        raise ValidationError("يجب ألا يتجاوز حجم الوثيقة 10 ميجابايت.")
    extension = Path(value.name).suffix.lower()
    if extension not in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError("صيغة الوثيقة غير مسموحة؛ استخدم PDF أو JPG أو PNG أو WEBP.")


def student_document_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    safe_extension = extension if extension in {".pdf", ".jpg", ".jpeg", ".png", ".webp"} else ""
    return (
        f"student-documents/{instance.school_id}/"
        f"{instance.student_id}/{uuid.uuid4().hex}{safe_extension}"
    )


class StudentDocument(TenantOwnedModel):
    """Private school-managed documents attached to a single student profile."""

    class DocumentType(models.TextChoices):
        BIRTH_CERTIFICATE = "birth_certificate", "شهادة ميلاد"
        IDENTITY = "identity", "هوية / إقامة"
        MEDICAL = "medical", "وثيقة طبية"
        ACADEMIC = "academic", "وثيقة أكاديمية"
        CUSTODY = "custody", "وثيقة ولاية / حضانة"
        OTHER = "other", "أخرى"

    student = models.ForeignKey(
        Student,
        verbose_name="الطالب",
        on_delete=models.PROTECT,
        related_name="documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="رفع الوثيقة",
        on_delete=models.PROTECT,
        related_name="uploaded_student_documents",
    )
    title = models.CharField("عنوان الوثيقة", max_length=180)
    document_type = models.CharField(
        "نوع الوثيقة", max_length=30, choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    file = models.FileField(
        "ملف الوثيقة",
        upload_to=student_document_upload_path,
        max_length=255,
        validators=[validate_student_document_file],
    )
    description = models.TextField("ملاحظات", blank=True)
    issued_on = models.DateField("تاريخ الإصدار", null=True, blank=True)
    expires_on = models.DateField("تاريخ الانتهاء", null=True, blank=True)
    visible_to_guardian = models.BooleanField("متاحة لولي الأمر المرتبط", default=True)

    class Meta:
        verbose_name = "وثيقة طالب"
        verbose_name_plural = "وثائق الطلاب"
        indexes = [
            models.Index(
                fields=["school", "student", "created_at"],
                name="stdoc_school_stud_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة المحددة للوثيقة."})
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValidationError({"expires_on": "تاريخ انتهاء الوثيقة يسبق تاريخ إصدارها."})


class GuardianConsent(TenantOwnedModel):
    """A traceable consent request that only the linked guardian can answer."""

    class ConsentType(models.TextChoices):
        TRIP = "trip", "رحلة / نشاط خارجي"
        MEDIA = "media", "تصوير ونشر"
        MEDICAL = "medical", "إجراء طبي"
        ACADEMIC = "academic", "إجراء أكاديمي"
        DATA = "data", "استخدام البيانات"
        GENERAL = "general", "موافقة عامة"

    class Status(models.TextChoices):
        PENDING = "pending", "بانتظار رد ولي الأمر"
        APPROVED = "approved", "تمت الموافقة"
        REJECTED = "rejected", "مرفوضة"
        CANCELED = "canceled", "ملغاة"
        EXPIRED = "expired", "منتهية"

    student = models.ForeignKey(
        Student,
        verbose_name="الطالب",
        on_delete=models.PROTECT,
        related_name="guardian_consents",
    )
    guardian = models.ForeignKey(
        Guardian,
        verbose_name="ولي الأمر المعني",
        on_delete=models.PROTECT,
        related_name="consent_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="منشئ طلب الموافقة",
        on_delete=models.PROTECT,
        related_name="created_guardian_consents",
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="صاحب الرد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responded_guardian_consents",
    )
    consent_type = models.CharField(
        "نوع الموافقة", max_length=20, choices=ConsentType.choices,
        default=ConsentType.GENERAL,
    )
    title = models.CharField("عنوان الطلب", max_length=180)
    details = models.TextField("تفاصيل الموافقة المطلوبة")
    status = models.CharField(
        "حالة الموافقة", max_length=12, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    requested_at = models.DateTimeField("وقت إرسال الطلب", default=timezone.now)
    expires_at = models.DateTimeField("موعد انتهاء الطلب", null=True, blank=True)
    responded_at = models.DateTimeField("وقت رد ولي الأمر", null=True, blank=True)
    response_note = models.TextField("ملاحظة ولي الأمر", blank=True)

    class Meta:
        verbose_name = "طلب موافقة ولي أمر"
        verbose_name_plural = "موافقات أولياء الأمور"
        indexes = [
            models.Index(
                fields=["school", "guardian", "status"],
                name="gcons_school_guard_stat_idx",
            ),
            models.Index(
                fields=["school", "student", "created_at"],
                name="gcons_school_stud_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة المحددة."})
        if self.guardian_id and self.guardian.school_id != self.school_id:
            raise ValidationError({"guardian": "ولي الأمر لا يتبع المدرسة المحددة."})
        if self.student_id and self.guardian_id and self.school_id:
            linked = StudentGuardianRelation.objects.filter(
                school_id=self.school_id,
                student_id=self.student_id,
                guardian_id=self.guardian_id,
                is_archived=False,
            ).exists()
            if not linked:
                raise ValidationError({"guardian": "ولي الأمر غير مرتبط بالطالب المحدد."})
        if self.expires_at and self.expires_at <= self.requested_at:
            raise ValidationError({"expires_at": "يجب أن يكون انتهاء الطلب بعد وقت إنشائه."})
        if self.status == self.Status.PENDING and self.responded_at is not None:
            raise ValidationError({"responded_at": "لا يمكن أن يكون الطلب بانتظار الرد مع وجود وقت استجابة."})
        if self.status in {self.Status.APPROVED, self.Status.REJECTED} and self.responded_at is None:
            raise ValidationError({"responded_at": "يجب تسجيل وقت الاستجابة للطلب الذي تم الرد عليه."})


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
