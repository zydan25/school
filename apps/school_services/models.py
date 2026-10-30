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
    """خطوط سير الحافلات المدرسية وسائقيها ومشرفيها والتعاقد المالي."""
    route_name = models.CharField("اسم خط السير", max_length=150)
    route_code = models.CharField("رمز الخط", max_length=50, db_index=True)
    destination_area = models.CharField("الوجهة / المنطقة المغطاة", max_length=200, blank=True)
    bus_number = models.CharField("رقم الحافلة / اللوحة", max_length=50)
    bus_capacity = models.PositiveSmallIntegerField("سعة الحافلة (مقاعد)", default=30)
    driver_name = models.CharField("اسم السائق", max_length=120)
    driver_phone = models.CharField("هاتف السائق", max_length=30)
    driver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب تسجيل الدخول للسائق (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="driven_buses",
    )
    supervisor_teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المشرف على الحافلة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supervised_buses",
    )
    supervisor_name = models.CharField("اسم مشرف/ة الحافلة (نصي)", max_length=120, blank=True)
    supervisor_phone = models.CharField("هاتف المشرف/ة", max_length=30, blank=True)
    morning_pickup_time = models.TimeField("وقت بداية الانطلاق الصباحي", null=True, blank=True)
    afternoon_dropoff_time = models.TimeField("وقت بداية رحلة العودة", null=True, blank=True)
    monthly_fee = models.DecimalField("رسوم اشتراك الطالب الشهري", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    # Financial Contract with Bus / Driver
    class CompensationType(models.TextChoices):
        MONTHLY_FLAT = "monthly_flat", "مبلغ شهري مقطوع ثابت"
        PER_STUDENT = "per_student", "عمولة / أجر شهري بحسب عدد الطلاب الركاب"

    class ContractorType(models.TextChoices):
        EMPLOYEE = "employee", "موظف في كادر المدرسة (راتب وسحوبات)"
        EXTERNAL = "external", "متعهد / سائق خارجي (ذمم موردين)"

    compensation_type = models.CharField(
        "طريقة احتساب مستحقات الباص",
        max_length=20,
        choices=CompensationType.choices,
        default=CompensationType.MONTHLY_FLAT,
    )
    contract_amount = models.DecimalField(
        "قيمة التعاقد (المبلغ المقطوع أو نصيب الراكب)",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    contractor_type = models.CharField(
        "صفة تعاقد السائق/الحافلة",
        max_length=20,
        choices=ContractorType.choices,
        default=ContractorType.EMPLOYEE,
    )
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
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "العام الدراسي لا ينتمي إلى هذه المدرسة."})
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
        if self._state.adding and self.status == self.Status.BORROWED:
            if self.book.available_copies <= 0:
                raise ValidationError({"book": "لا توجد نسخ متاحة حالياً من هذا الكتاب للإعارة."})

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        previous_status = None
        if not is_new and self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()

        from django.db import transaction
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new and self.status == self.Status.BORROWED:
                if self.book.available_copies > 0:
                    self.book.available_copies -= 1
                    self.book.save(update_fields=["available_copies"])
            elif previous_status != self.Status.RETURNED and self.status == self.Status.RETURNED:
                if self.book.available_copies < self.book.total_copies:
                    self.book.available_copies += 1
                    self.book.save(update_fields=["available_copies"])


# -----------------------------------------------------------------------------
# 3. Transportation Financial Settlements (المحاسبة المالية للحافلات والسائقين)
# -----------------------------------------------------------------------------

class BusFinancialSettlement(TenantOwnedModel):
    """
    سجل المحاسبة المالية للحافلة والسائق.
    يحاسب السائق/المتعهد إما كموظف أو متعهد، وبحسب عدد الطلاب أو مبلغ مقطوع،
    مع رصد السحوبات والمستحقات والربط بالقيود وسندات الصرف.
    """
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة تسوية"
        APPROVED = "approved", "معتمدة"
        PAID = "paid", "مصروفة بالكامل"

    bus_route = models.ForeignKey(
        BusRoute,
        verbose_name="خط السير / الحافلة",
        on_delete=models.PROTECT,
        related_name="settlements",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="bus_settlements",
    )
    month = models.PositiveSmallIntegerField("الشهر المالي (1-12)")
    year = models.PositiveSmallIntegerField("السنة المالية (مثال: 2026)")
    settlement_date = models.DateField("تاريخ التسوية", default=timezone.localdate)
    student_count = models.PositiveSmallIntegerField("عدد الطلاب الركاب الفعلي", default=0)
    rate_applied = models.DecimalField("معدل الاحتساب المطبق", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    gross_due = models.DecimalField("إجمالي المستحق للسائق/المتعهد", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    advances_withdrawn = models.DecimalField("إجمالي السحوبات والدفعات المقدمة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_payable = models.DecimalField("صافي المبلغ المتبقي المستحق", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة التسوية", max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_bus_settlements",
    )
    payment_voucher = models.ForeignKey(
        "accounting.PaymentVoucher",
        verbose_name="سند الصرف المالي المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bus_settlements",
    )
    notes = models.TextField("ملاحظات وشرح التسوية", blank=True)

    class Meta:
        verbose_name = "تسوية مالية لحافلة"
        verbose_name_plural = "المحاسبة المالية للحافلات والسائقين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "bus_route", "academic_year", "year", "month"],
                condition=models.Q(is_archived=False),
                name="school_services_bus_settlement_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"تسوية {self.bus_route.bus_number} - شهر {self.month}/{self.year}: صافي {self.net_payable}"

    def calculate_due(self):
        """احتساب المستحق آلياً بحسب طريقة التعاقد وعدد الطلاب المسجلين."""
        active_subs = self.bus_route.student_subscriptions.filter(
            status=StudentBusSubscription.Status.ACTIVE,
            academic_year=self.academic_year,
            is_archived=False,
        ).count()
        self.student_count = active_subs
        self.rate_applied = self.bus_route.contract_amount

        if self.bus_route.compensation_type == BusRoute.CompensationType.PER_STUDENT:
            self.gross_due = Decimal(self.student_count) * self.rate_applied
        else:
            self.gross_due = self.rate_applied

        self.net_payable = max(Decimal("0.00"), self.gross_due - self.advances_withdrawn)


# -----------------------------------------------------------------------------
# 4. Student Textbooks & Fee Delivery (توزيع الكتب والرسوم الخاصة)
# -----------------------------------------------------------------------------

class StudentBookDistribution(TenantOwnedModel):
    """
    تسليم وتوزيع الكتب المدرسية والرسوم الخاصة بها على الطلاب.
    يتيح متابعة استلام كل طالب للكتب ورسومها وتحديث الفاتورة المالية.
    """
    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "بانتظار الصرف والتسليم"
        DELIVERED = "delivered", "تم التسليم للطالب"
        RETURNED = "returned", "مسترجع للمستودع"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="book_distributions",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="book_distributions",
    )
    book_title = models.CharField("اسم الكتاب / الحزمة المدرسية", max_length=200)
    fee_amount = models.DecimalField("قيمة رسم الكتاب المقيد على الطالب", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_status = models.CharField("حالة التسليم", max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    delivered_at = models.DateTimeField("تاريخ ووقت التسليم الفعلي", null=True, blank=True)
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="الموظف المسلّم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivered_books",
    )
    invoice = models.ForeignKey(
        "student_fees.StudentInvoice",
        verbose_name="الفاتورة المقيد عليها الرسم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_distributions",
    )
    notes = models.TextField("ملاحظات التسليم", blank=True)

    class Meta:
        verbose_name = "تسليم كتب مدرسية"
        verbose_name_plural = "توزيع الكتب المدرسية ورسومها"

    def __str__(self) -> str:
        return f"{self.student.first_name}: {self.book_title} [{self.get_delivery_status_display()}]"


# -----------------------------------------------------------------------------
# 5. School Clinic & Health (العيادة المدرسية وصحة الطلاب)
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
