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
                book = LibraryBook.objects.select_for_update().get(pk=self.book_id)
                if book.available_copies <= 0:
                    raise ValidationError({"book": "لا توجد نسخ متاحة حالياً من هذا الكتاب للإعارة."})
                book.available_copies -= 1
                book.save(update_fields=["available_copies"])
            elif previous_status != self.Status.RETURNED and self.status == self.Status.RETURNED:
                book = LibraryBook.objects.select_for_update().get(pk=self.book_id)
                if book.available_copies < book.total_copies:
                    book.available_copies += 1
                    book.save(update_fields=["available_copies"])


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

    def approve_and_create_payment_voucher(self, approved_by_user=None):
        """اعتماد التسوية المالية وتوليد سند صرف مالي وربطه محاسبياً."""
        if self.status == self.Status.APPROVED and self.payment_voucher:
            return self.payment_voucher

        from django.db import transaction

        from apps.accounting.models import Account, PaymentVoucher

        with transaction.atomic():
            self.calculate_due()
            self.status = self.Status.APPROVED
            if approved_by_user:
                self.approved_by = approved_by_user

            if self.net_payable > Decimal("0.00") and not self.payment_voucher:
                expense_acc = Account.objects.filter(school=self.school, code="5205", is_leaf=True).first()
                cash_acc = Account.objects.filter(school=self.school, code="1101", is_leaf=True).first()

                if expense_acc and cash_acc:
                    v_num = f"PV-BUS-{self.bus_route.bus_number}-{self.year}-{self.month:02d}"
                    pv, _ = PaymentVoucher.objects.get_or_create(
                        school=self.school,
                        voucher_number=v_num,
                        defaults={
                            "date": self.settlement_date,
                            "paid_to": f"السائق: {self.bus_route.driver_name} (حافلة {self.bus_route.bus_number})",
                            "amount": self.net_payable,
                            "debit_account": expense_acc,
                            "credit_account": cash_acc,
                            "description": f"مستحقات نقل مدرسي شهر {self.month}/{self.year} - {self.student_count} طالب",
                            "status": PaymentVoucher.Status.POSTED,
                        },
                    )
                    self.payment_voucher = pv
                    from apps.accounting.services.auto_posting import (
                        post_payment_voucher_to_journal,
                    )
                    if not pv.journal_entry_id:
                        post_payment_voucher_to_journal(pv)

            self.save()
            return self.payment_voucher


# -----------------------------------------------------------------------------
# 4. Student Textbooks & Fee Delivery (توزيع الكتب والرسوم الخاصة)
# -----------------------------------------------------------------------------

class StudentBookDistribution(TenantOwnedModel):
    """
    تسليم وتوزيع الكتب المدرسية والرسوم الخاصة بها على الطلاب.
    يتيح متابعة استلام كل طالب للكتب ورسومها وتحديث المخزون والفاتورة المالية.
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
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        verbose_name="الصنف المخزني المرتبط (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_distributions",
    )
    book_title = models.CharField("اسم الكتاب / الحزمة المدرسية", max_length=200)
    quantity = models.DecimalField("الكمية المسلمة", max_digits=6, decimal_places=2, default=Decimal("1.00"))
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
    returned_at = models.DateTimeField("تاريخ ووقت الاسترجاع", null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="الموظف المستلم للاسترجاع",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="returned_books",
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
        return f"{self.student.first_name}: {self.book_title} (كمية: {self.quantity}) [{self.get_delivery_status_display()}]"

    def deliver_book(self, user=None):
        """تسليم الكتاب للطالب وخصم الكمية من المخزون وتوثيق العملية مع قفل تشاؤمي."""
        from django.db import transaction
        with transaction.atomic():
            locked_dist = StudentBookDistribution.objects.select_for_update().get(pk=self.pk)
            if locked_dist.delivery_status == self.DeliveryStatus.DELIVERED:
                return
            if locked_dist.inventory_item:
                from apps.inventory.models import InventoryItem, StockMovement
                item = InventoryItem.objects.select_for_update().get(pk=locked_dist.inventory_item_id)
                if item.current_stock < locked_dist.quantity:
                    raise ValidationError(f"رصيد الكتاب المخزني ({item.current_stock}) غير كافٍ لصرف كمية ({locked_dist.quantity}).")
                StockMovement.objects.create(
                    school=locked_dist.school,
                    item=item,
                    movement_type=StockMovement.MovementType.ISSUE,
                    quantity=locked_dist.quantity,
                    unit_cost=item.unit_cost,
                    recipient_name=f"الطالب: {locked_dist.student}",
                    reference=f"تسليم كتاب للطالب {locked_dist.student.student_id_number}",
                )
            # الربط المالي التلقائي: إنشاء فاتورة رسوم الكتاب إن وجدت قيمة للرسم
            if locked_dist.fee_amount > Decimal("0.00") and not locked_dist.invoice:
                from apps.student_fees.models import FeeCategory, StudentInvoice, StudentInvoiceItem
                from apps.accounting.services.auto_posting import post_student_invoice_to_journal
                import uuid
                cat, _ = FeeCategory.objects.get_or_create(
                    school=locked_dist.school,
                    code="BOOKS",
                    defaults={"name": "رسوم الكتب والمستلزمات الدراسية", "is_mandatory": False},
                )
                inv = StudentInvoice.objects.create(
                    school=locked_dist.school,
                    student=locked_dist.student,
                    academic_year=locked_dist.academic_year,
                    invoice_number=f"INV-BOOK-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                    issue_date=timezone.localdate(),
                    due_date=timezone.localdate(),
                    total_amount=locked_dist.fee_amount,
                )
                StudentInvoiceItem.objects.create(
                    school=locked_dist.school,
                    invoice=inv,
                    fee_category=cat,
                    description=f"كتاب: {locked_dist.book_title} (عدد {locked_dist.quantity})",
                    amount=locked_dist.fee_amount,
                )
                invoice_entry = post_student_invoice_to_journal(inv)
                if invoice_entry and not inv.journal_entry_id:
                    inv.journal_entry = invoice_entry
                    inv.save(update_fields=["journal_entry", "updated_at"])
                locked_dist.invoice = inv
                self.invoice = inv

            locked_dist.delivery_status = self.DeliveryStatus.DELIVERED
            locked_dist.delivered_at = timezone.now()
            if user:
                locked_dist.delivered_by = user
            locked_dist.save(update_fields=["delivery_status", "delivered_at", "delivered_by", "invoice", "updated_at"])
            self.delivery_status = locked_dist.delivery_status
            self.delivered_at = locked_dist.delivered_at
            self.delivered_by = locked_dist.delivered_by

    def return_book(self, user=None):
        """استرجاع الكتاب إلى المخزون وتحديث حالته والتسوية المالية مع قفل تشاؤمي."""
        from django.db import transaction
        with transaction.atomic():
            locked_dist = StudentBookDistribution.objects.select_for_update().get(pk=self.pk)
            if locked_dist.delivery_status != self.DeliveryStatus.DELIVERED:
                return
            if locked_dist.inventory_item:
                from apps.inventory.models import InventoryItem, StockMovement
                item = InventoryItem.objects.select_for_update().get(pk=locked_dist.inventory_item_id)
                StockMovement.objects.create(
                    school=locked_dist.school,
                    item=item,
                    movement_type=StockMovement.MovementType.RECEIPT,
                    quantity=locked_dist.quantity,
                    unit_cost=item.unit_cost,
                    recipient_name=f"استرجاع من الطالب: {locked_dist.student}",
                    reference=f"استرجاع كتاب من الطالب {locked_dist.student.student_id_number}",
                )

            # معالجة الأثر المالي عند استرجاع الكتاب
            if locked_dist.invoice_id:
                from apps.student_fees.models import StudentInvoice
                inv = StudentInvoice.objects.select_for_update().get(pk=locked_dist.invoice_id)
                if inv.paid_amount > Decimal("0.00"):
                    raise ValidationError(
                        "لا يمكن استرجاع الكتاب مالياً قبل عكس سندات القبض المرتبطة وإعادة الفاتورة إلى رصيد غير مسدد."
                    )
                if inv.journal_entry_id:
                    from apps.accounting.services.auto_posting import reverse_journal_entry
                    reverse_journal_entry(
                        inv.journal_entry,
                        reason=f"إلغاء رسوم استرجاع الكتاب: {locked_dist.book_title}",
                        reversed_by=user,
                    )
                inv.status = StudentInvoice.Status.CANCELLED
                inv.save(update_fields=["status", "updated_at"])

            locked_dist.delivery_status = self.DeliveryStatus.RETURNED
            locked_dist.returned_at = timezone.now()
            if user:
                locked_dist.returned_by = user
            locked_dist.save(update_fields=["delivery_status", "returned_at", "returned_by", "updated_at"])
            self.delivery_status = locked_dist.delivery_status
            self.returned_at = locked_dist.returned_at
            self.returned_by = locked_dist.returned_by


class BookRequisitionOrder(TenantOwnedModel):
    """
    أمر صرف وطلب توريد كتب من المستودع المدرسي.
    دورة عمل معتمدة: يرفع المعلم أو المشرف الطلب للشعبة، تعتمده الإدارة، ويصرفه أمين المستودع.
    """
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة طلب"
        SUBMITTED = "submitted", "مرفوع للاعتماد الإداري"
        APPROVED = "approved", "معتمد - موجه لأمين المستودع"
        FULFILLED = "fulfilled", "تم الصرف والتسليم من المخزن"
        REJECTED = "rejected", "مرفوض"

    order_number = models.CharField("رقم أمر الصرف", max_length=50, db_index=True)
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="book_orders",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي المستفيد",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="book_orders",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية المستفيدة",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="book_orders",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="محرر الطلب (المشرف / المعلم)",
        on_delete=models.PROTECT,
        related_name="requested_book_orders",
    )
    status = models.CharField("حالة أمر الصرف", max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المسؤول المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_book_orders",
    )
    approved_at = models.DateTimeField("تاريخ الاعتماد الإداري", null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="أمين المستودع الصارف",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfilled_book_orders",
    )
    fulfilled_at = models.DateTimeField("تاريخ الصرف من المخزن", null=True, blank=True)
    notes = models.TextField("ملاحظات أمر الصرف", blank=True)

    class Meta:
        verbose_name = "أمر صرف كتب ومستلزمات"
        verbose_name_plural = "أوامر صرف الكتب من المستودع"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "order_number"],
                condition=models.Q(is_archived=False),
                name="school_services_book_order_uniq",
            )
        ]

    def __str__(self) -> str:
        beneficiary = self.section or self.grade_level or "عام"
        return f"أمر صرف #{self.order_number} ({beneficiary}): {self.get_status_display()}"


class BookRequisitionItem(TenantOwnedModel):
    """البنود والكتب المطلوبة في أمر الصرف."""
    requisition = models.ForeignKey(
        BookRequisitionOrder,
        verbose_name="أمر الصرف التابع له",
        on_delete=models.CASCADE,
        related_name="items",
    )
    book_title = models.CharField("اسم الكتاب / المادة المنهجية", max_length=200)
    quantity_requested = models.PositiveIntegerField("الكمية المطلوبة (نسخ)")
    quantity_approved = models.PositiveIntegerField("الكمية المعتمدة", default=0)
    quantity_dispatched = models.PositiveIntegerField("الكمية المصروفة فعلياً", default=0)
    notes = models.CharField("ملاحظات البند", max_length=255, blank=True)

    class Meta:
        verbose_name = "بند أمر صرف كتب"
        verbose_name_plural = "بنود أوامر صرف الكتب"

    def __str__(self) -> str:
        return f"{self.book_title}: {self.quantity_dispatched}/{self.quantity_requested} نسخة"


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
