"""Student fees, invoicing, installment plans, and payment receipt domain models."""
from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class FeeCategory(TenantOwnedModel):
    """بنود وتصنيفات الرسوم المدرسية (رسوم دراسية، نقل، كتب، زي)."""
    name = models.CharField("اسم بند الرسوم", max_length=150)
    code = models.CharField("رمز البند", max_length=50)
    description = models.TextField("وصف البند", blank=True)
    is_mandatory = models.BooleanField("بند إلزامي لكافة الطلاب", default=True)

    class Meta:
        verbose_name = "بند رسوم"
        verbose_name_plural = "بنود وتصنيفات الرسوم"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="student_fees_cat_school_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class FeeStructure(TenantOwnedModel):
    """هيكل الرسوم السنوي المعتمد لكل صف دراسي."""
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="fee_structures",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي",
        on_delete=models.PROTECT,
        related_name="fee_structures",
    )
    fee_category = models.ForeignKey(
        FeeCategory,
        verbose_name="بند الرسوم",
        on_delete=models.PROTECT,
        related_name="structures",
    )
    amount = models.DecimalField("قيمة الرسم المالي", max_digits=12, decimal_places=2)
    due_date = models.DateField("موعد استحقاق السداد الافتراضي", null=True, blank=True)

    class Meta:
        verbose_name = "هيكل رسوم صف"
        verbose_name_plural = "هياكل الرسوم الدراسية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "grade_level", "fee_category"],
                condition=models.Q(is_archived=False),
                name="student_fees_structure_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.grade_level.name} - {self.fee_category.name}: {self.amount}"


class StudentInvoice(TenantOwnedModel):
    """فاتورة المطالبة المالية للطالب."""
    class Status(models.TextChoices):
        UNPAID = "unpaid", "غير مسددة"
        PARTIAL = "partially_paid", "مسددة جزئياً"
        PAID = "paid", "مسددة بالكامل"
        CANCELLED = "cancelled", "ملغاة"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المطالب",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="student_invoices",
    )
    invoice_number = models.CharField("رقم الفاتورة", max_length=50, db_index=True)
    total_amount = models.DecimalField("إجمالي قيمة الفاتورة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField("إجمالي الخصومات والمنح", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField("المبلغ المسدد حتى الآن", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة الفاتورة", max_length=20, choices=Status.choices, default=Status.UNPAID)
    issue_date = models.DateField("تاريخ إصدار الفاتورة", default=timezone.localdate)
    due_date = models.DateField("تاريخ الاستحقاق")

    class Meta:
        verbose_name = "فاتورة طالب"
        verbose_name_plural = "فواتير الطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "invoice_number"],
                condition=models.Q(is_archived=False),
                name="student_fees_invoice_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "student", "status"]),
            models.Index(fields=["school", "due_date"]),
        ]

    def __str__(self) -> str:
        return f"فاتورة #{self.invoice_number} - {self.student}: {self.total_amount} ({self.get_status_display()})"

    @property
    def remaining_amount(self) -> Decimal:
        net_payable = max(Decimal("0.00"), self.total_amount - self.discount_amount)
        return max(Decimal("0.00"), net_payable - self.paid_amount)

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})


class StudentInvoiceItem(TenantOwnedModel):
    """البنود التفصيلية داخل فاتورة الطالب."""
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة التابعة لها",
        on_delete=models.CASCADE,
        related_name="items",
    )
    fee_category = models.ForeignKey(
        FeeCategory,
        verbose_name="بند الرسم",
        on_delete=models.PROTECT,
        related_name="invoice_items",
    )
    description = models.CharField("بيان البند", max_length=255)
    amount = models.DecimalField("القيمة الإجمالية", max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField("قيمة الخصم إن وجد", max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "بند فاتورة"
        verbose_name_plural = "بنود فواتير الطلاب"

    def __str__(self) -> str:
        return f"{self.description}: {self.amount}"


class PaymentReceipt(TenantOwnedModel):
    """سند القبض والتحصيل المالي من الطالب / ولي الأمر."""
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقداً (صندوق المدرسة)"
        BANK_TRANSFER = "bank_transfer", "تحويل بنكي"
        POS = "pos", "شبكة / نقطة بيع"
        ONLINE = "online", "دفع إلكتروني مباشر"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المسدد",
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة المرتبطة بالسداد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receipts",
    )
    receipt_number = models.CharField("رقم سند القبض", max_length=50, db_index=True)
    amount = models.DecimalField("المبلغ المحصل", max_digits=12, decimal_places=2)
    payment_method = models.CharField("طريقة الدفع", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference_number = models.CharField("رقم الإيداع / مرجع العملية البنكية", max_length=100, blank=True)
    paid_at = models.DateTimeField("تاريخ ووقت السداد", default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="أمين الصندوق / المحصل",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collected_receipts",
    )
    notes = models.TextField("ملاحظات إضافية على السند", blank=True)

    class Meta:
        verbose_name = "سند قبض"
        verbose_name_plural = "سندات القبض والتحصيل"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "receipt_number"],
                condition=models.Q(is_archived=False),
                name="student_fees_receipt_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "paid_at"]),
            models.Index(fields=["school", "student"]),
        ]

    def __str__(self) -> str:
        return f"سند #{self.receipt_number} - {self.student}: {self.amount} ({self.get_payment_method_display()})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            # Auto-update linked invoice or allocate to student's open invoices
            from django.db import transaction
            with transaction.atomic():
                if self.invoice:
                    inv = StudentInvoice.objects.select_for_update().get(pk=self.invoice_id)
                    inv.paid_amount += self.amount
                    net = max(Decimal("0.00"), inv.total_amount - inv.discount_amount)
                    if inv.paid_amount >= net:
                        inv.status = StudentInvoice.Status.PAID
                    elif inv.paid_amount > Decimal("0.00"):
                        inv.status = StudentInvoice.Status.PARTIAL
                    inv.save(update_fields=["paid_amount", "status", "updated_at"])
                else:
                    # Allocate chronologically across open unpaid invoices
                    remaining = self.amount
                    open_invoices = StudentInvoice.objects.filter(
                        school=self.school,
                        student=self.student,
                        status__in=[StudentInvoice.Status.UNPAID, StudentInvoice.Status.PARTIAL],
                        is_archived=False,
                    ).order_by("due_date", "created_at").select_for_update()

                    for inv in open_invoices:
                        if remaining <= Decimal("0.00"):
                            break
                        net = max(Decimal("0.00"), inv.total_amount - inv.discount_amount)
                        needed = max(Decimal("0.00"), net - inv.paid_amount)
                        pay_part = min(remaining, needed)
                        inv.paid_amount += pay_part
                        remaining -= pay_part
                        if inv.paid_amount >= net:
                            inv.status = StudentInvoice.Status.PAID
                        else:
                            inv.status = StudentInvoice.Status.PARTIAL
                        inv.save(update_fields=["paid_amount", "status", "updated_at"])


class FeeInstallmentPlan(TenantOwnedModel):
    """خطة تقسيط الرسوم الدراسية المعتمدة للطالب."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="installment_plans",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة المرتبطة",
        on_delete=models.CASCADE,
        related_name="installment_plans",
    )
    plan_name = models.CharField("اسم خطة التقسيط (مثال: تقسيط ربع سنوي)", max_length=150)
    total_amount = models.DecimalField("إجمالي مبلغ الخطة", max_digits=12, decimal_places=2)
    number_of_installments = models.PositiveSmallIntegerField("عدد الأقساط", default=3)
    notes = models.TextField("ملاحظات وشروط الاتفاق", blank=True)

    class Meta:
        verbose_name = "خطة تقسيط رسوم"
        verbose_name_plural = "خطط تقسيط الرسوم"

    def __str__(self) -> str:
        return f"{self.plan_name} - {self.student}: {self.total_amount}"


class FeeInstallment(TenantOwnedModel):
    """القسط الفردي ضمن خطة تقسيط رسوم الطالب."""
    class Status(models.TextChoices):
        PENDING = "pending", "مستحق (قيد السداد)"
        PAID = "paid", "مسدد بالكامل"
        OVERDUE = "overdue", "متأخر عن موعد الاستحقاق"

    plan = models.ForeignKey(
        FeeInstallmentPlan,
        verbose_name="خطة التقسيط",
        on_delete=models.CASCADE,
        related_name="installments",
    )
    installment_number = models.PositiveSmallIntegerField("رقم القسط (1, 2, 3...)")
    title = models.CharField("بيان القسط (مثل: قسط شهر نوفمبر)", max_length=150)
    amount = models.DecimalField("مبلغ القسط", max_digits=12, decimal_places=2)
    due_date = models.DateField("تاريخ الاستحقاق")
    paid_date = models.DateField("تاريخ السداد الفعلي", null=True, blank=True)
    status = models.CharField("حالة القسط", max_length=20, choices=Status.choices, default=Status.PENDING)
    receipt = models.ForeignKey(
        PaymentReceipt,
        verbose_name="سند السداد المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installments",
    )

    class Meta:
        verbose_name = "قسط مالي مجدول"
        verbose_name_plural = "الأقساط المالية المجدولة"
        ordering = ["due_date", "installment_number"]

    def __str__(self) -> str:
        return f"قسط #{self.installment_number} ({self.title}) - {self.amount} [{self.get_status_display()}]"
