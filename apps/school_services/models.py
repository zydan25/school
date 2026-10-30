"""School support services models: Transportation, Library, and Health Clinic."""
from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


# -----------------------------------------------------------------------------
# 1. School Transportation (النقل المدرسي والحافلات)
# -----------------------------------------------------------------------------

class BusRoute(TenantOwnedModel):
    """خطوط سير الحافلات المدرسية وسائقيها ومشرفيها."""
    route_name = models.CharField("اسم خط السير", max_length=150)
    route_code = models.CharField("رمز الخط", max_length=50, db_index=True)
    bus_number = models.CharField("رقم الحافلة / اللوحة", max_length=50)
    bus_capacity = models.PositiveSmallIntegerField("سعة الحافلة (مقاعد)", default=30)
    driver_name = models.CharField("اسم السائق", max_length=120)
    driver_phone = models.CharField("هاتف السائق", max_length=30)
    supervisor_name = models.CharField("اسم مشرف/ة الحافلة", max_length=120, blank=True)
    supervisor_phone = models.CharField("هاتف المشرف/ة", max_length=30, blank=True)
    morning_pickup_time = models.TimeField("وقت بداية الانطلاق الصباحي", null=True, blank=True)
    afternoon_dropoff_time = models.TimeField("وقت بداية رحلة العودة", null=True, blank=True)
    monthly_fee = models.DecimalField("رسوم الاشتراك الشهري", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField("خط نشط وسارٍ", default=True)

    class Meta:
        verbose_name = "خط سير حافلة"
        verbose_name_plural = "خطوط النقل المدرسي"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "route_code"],
                condition=models.Q(is_archived=False),
                name="services_bus_route_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.route_name} [{self.route_code}] - حافلة ({self.bus_number})"


class StudentBusSubscription(TenantOwnedModel):
    """اشتراكات الطلاب في خدمة النقل المدرسي."""
    class SubscriptionType(models.TextChoices):
        TWO_WAY = "two_way", "ذهاب وعودة (كامل)"
        MORNING_ONLY = "morning_only", "صباحي فقط (ذهاب)"
        AFTERNOON_ONLY = "afternoon_only", "مسائي فقط (عودة)"

    class Status(models.TextChoices):
        ACTIVE = "active", "سارٍ ونشط"
        SUSPENDED = "suspended", "موقوف مؤقتاً"
        CANCELLED = "cancelled", "ملغى"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المشترك",
        on_delete=models.CASCADE,
        related_name="bus_subscriptions",
    )
    bus_route = models.ForeignKey(
        BusRoute,
        verbose_name="خط السير",
        on_delete=models.PROTECT,
        related_name="student_subscriptions",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="bus_subscriptions",
    )
    subscription_type = models.CharField(
        "نوع الاشتراك",
        max_length=20,
        choices=SubscriptionType.choices,
        default=SubscriptionType.TWO_WAY,
    )
    pickup_address = models.TextField("عنوان نقطة الالتقاط والمنزل بالتفصيل", blank=True)
    status = models.CharField("حالة الاشتراك", max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = "اشتراك نقل طالب"
        verbose_name_plural = "اشتراكات النقل المدرسي للطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "academic_year"],
                condition=models.Q(is_archived=False),
                name="services_student_bus_sub_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student}: {self.bus_route.route_name} ({self.get_subscription_type_display()})"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا ينتمي إلى هذه المدرسة."})
        if self.bus_route_id and self.bus_route.school_id != self.school_id:
            raise ValidationError({"bus_route": "خط النقل لا ينتمي إلى هذه المدرسة."})


# -----------------------------------------------------------------------------
# 2. School Library (المكتبة المدرسية واستعارة الكتب)
# -----------------------------------------------------------------------------

class LibraryBook(TenantOwnedModel):
    """دليل الكتب والمراجع في المكتبة المدرسية."""
    isbn = models.CharField("الرقم المعياري الدولي (ISBN / الرمز)", max_length=50, blank=True, db_index=True)
    title = models.CharField("عنوان الكتاب / المرجع", max_length=250)
    author = models.CharField("المؤلف", max_length=150, blank=True)
    publisher = models.CharField("دار النشر", max_length=150, blank=True)
    category = models.CharField("التصنيف أو الفن (علمي، أدبي، إسلامي، روايات)", max_length=100, blank=True)
    publication_year = models.PositiveSmallIntegerField("سنة النشر", null=True, blank=True)
    total_copies = models.PositiveSmallIntegerField("إجمالي النسخ المتوفرة", default=1)
    available_copies = models.PositiveSmallIntegerField("النسخ المتاحة حالياً للإعارة", default=1)
    shelf_location = models.CharField("موقع الرف والقاعة", max_length=100, blank=True)

    class Meta:
        verbose_name = "كتاب مدرسي / مرجع"
        verbose_name_plural = "المكتبة المدرسية والكتب"

    def __str__(self) -> str:
        return f"{self.title} - {self.author} (متاح: {self.available_copies}/{self.total_copies})"


class BookLoan(TenantOwnedModel):
    """سجل استعارة الكتب للطلاب أو المعلمين."""
    class Status(models.TextChoices):
        BORROWED = "borrowed", "معار حالياً"
        RETURNED = "returned", "مسترجع بالكامل"
        OVERDUE = "overdue", "متأخر عن موعد الإرجاع"
        LOST = "lost", "مفقود أو تالف"

    book = models.ForeignKey(
        LibraryBook,
        verbose_name="الكتاب المستعار",
        on_delete=models.PROTECT,
        related_name="loans",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المستعير (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_loans",
    )
    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المستعير (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_loans",
    )
    borrow_date = models.DateField("تاريخ الاستعارة", default=timezone.localdate)
    due_date = models.DateField("تاريخ الاستحقاق والإرجاع")
    return_date = models.DateField("تاريخ الإرجاع الفعلي", null=True, blank=True)
    status = models.CharField("حالة الإعارة", max_length=20, choices=Status.choices, default=Status.BORROWED)
    fine_amount = models.DecimalField("غرامة التأخير أو التلف (إن وجدت)", max_digits=8, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField("ملاحظات أمين المكتبة", blank=True)

    class Meta:
        verbose_name = "سجل إعارة كتاب"
        verbose_name_plural = "إعارات المكتبة المدرسية"

    def __str__(self) -> str:
        borrower = self.student or self.teacher or "مستعير غير محدد"
        return f"{self.book.title} -> {borrower} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if not self.student and not self.teacher:
            raise ValidationError("يجب تحديد المستعير (طالب أو معلم).")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and self.status == self.Status.BORROWED:
            if self.book.available_copies > 0:
                self.book.available_copies -= 1
                self.book.save(update_fields=["available_copies"])
        elif self.status == self.Status.RETURNED and self.return_date:
            if self.book.available_copies < self.book.total_copies:
                self.book.available_copies += 1
                self.book.save(update_fields=["available_copies"])


# -----------------------------------------------------------------------------
# 3. School Clinic & Health (العيادة المدرسية وصحة الطلاب)
# -----------------------------------------------------------------------------

class StudentHealthProfile(TenantOwnedModel):
    """الملف الصحي والوقائي للطالب والتنبيهات المرضية."""
    student = models.OneToOneField(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    blood_type = models.CharField("فصيلة الدم", max_length=10, blank=True)
    chronic_conditions = models.TextField("الأمراض المزمنة (إن وجدت)", blank=True)
    allergies = models.TextField("الحساسية الدوائية أو الغذائية", blank=True)
    daily_medications = models.TextField("الأدوية اليومية والجرعات", blank=True)
    emergency_contact_name = models.CharField("اسم جهة الاتصال للطوارئ", max_length=120)
    emergency_contact_phone = models.CharField("هاتف الطوارئ البديل", max_length=30)
    general_notes = models.TextField("ملاحظات صحية عامة وتوصيات", blank=True)

    class Meta:
        verbose_name = "ملف صحي لطالب"
        verbose_name_plural = "الملفات الصحية للطلاب"

    def __str__(self) -> str:
        return f"الملف الصحي - {self.student}: {self.blood_type or 'غير محدد'}"


class ClinicVisit(TenantOwnedModel):
    """زيارات العيادة المدرسية والإسعافات الأولية."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المراجع",
        on_delete=models.CASCADE,
        related_name="clinic_visits",
    )
    visit_date = models.DateTimeField("تاريخ ووقت الزيارة", default=timezone.now)
    symptoms = models.TextField("الأعراض والشكوى")
    diagnosis = models.TextField("التشخيص التقديري", blank=True)
    treatment_given = models.TextField("الإسعافات أو العلاج المقدم", blank=True)
    temperature = models.DecimalField("درجة الحرارة (إن قيست)", max_digits=4, decimal_places=1, null=True, blank=True)
    sent_home = models.BooleanField("تم صرف الطالب إلى المنزل", default=False)
    parent_notified = models.BooleanField("تم إشعار ولي الأمر هاتفياً / رسالة", default=False)
    attended_by = models.CharField("المشرف / الممرض المعالج", max_length=120, blank=True)
    notes = models.TextField("ملاحظات إضافية وتوصيات للمتابعة", blank=True)

    class Meta:
        verbose_name = "زيارة عيادة مدرسية"
        verbose_name_plural = "سجل زيارات العيادة المدرسية"

    def __str__(self) -> str:
        return f"زيارة عيادة: {self.student} - {self.visit_date.strftime('%Y-%m-%d %H:%M')}"
