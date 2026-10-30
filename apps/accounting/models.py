"""Double-entry accounting, chart of accounts, and ledger domain models."""
from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class FiscalYear(TenantOwnedModel):
    """السنة المالية المستقلة للمدرسة."""
    name = models.CharField("اسم السنة المالية", max_length=100)
    start_date = models.DateField("تاريخ بداية السنة المالية")
    end_date = models.DateField("تاريخ نهاية السنة المالية")
    is_closed = models.BooleanField("سنة مقفلة محاسبياً", default=False)

    class Meta:
        verbose_name = "سنة مالية"
        verbose_name_plural = "السنوات المالية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                condition=models.Q(is_archived=False),
                name="accounting_fiscal_year_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({'مقفلة' if self.is_closed else 'مفتوحة'})"


class FiscalPeriod(TenantOwnedModel):
    """الفترات المحاسبية الشهرية أو الربع سنوية التابعة للسنة المالية."""
    fiscal_year = models.ForeignKey(
        FiscalYear,
        verbose_name="السنة المالية",
        on_delete=models.PROTECT,
        related_name="periods",
    )
    period_number = models.PositiveSmallIntegerField("رقم الفترة")
    name = models.CharField("اسم الفترة (مثل: يناير 2026)", max_length=100)
    start_date = models.DateField("تاريخ بداية الفترة")
    end_date = models.DateField("تاريخ نهاية الفترة")
    is_closed = models.BooleanField("فترة مقفلة", default=False)

    class Meta:
        verbose_name = "فترة محاسبية"
        verbose_name_plural = "الفترات المحاسبية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "fiscal_year", "period_number"],
                condition=models.Q(is_archived=False),
                name="accounting_period_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.fiscal_year.name} - {self.name}"


class Account(TenantOwnedModel):
    """دليل الحسابات (شجرة الحسابات المستقلة لكل مدرسة)."""
    class AccountType(models.TextChoices):
        ASSET = "asset", "أصول (Assets)"
        LIABILITY = "liability", "التزامات (Liabilities)"
        EQUITY = "equity", "حقوق الملكية (Equity)"
        REVENUE = "revenue", "إيرادات (Revenues)"
        EXPENSE = "expense", "مصروفات (Expenses)"

    code = models.CharField("رمز الحساب المحاسبي", max_length=50, db_index=True)
    name = models.CharField("اسم الحساب", max_length=200)
    account_type = models.CharField("نوع الحساب", max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey(
        "self",
        verbose_name="الحساب الأب (للهيكل الشجري)",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    is_leaf = models.BooleanField("حساب تفصيلي يقبل الترحيل المباشر", default=True)

    class Meta:
        verbose_name = "حساب مالي"
        verbose_name_plural = "دليل الحسابات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="accounting_account_code_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "account_type"]),
            models.Index(fields=["school", "is_leaf"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class CostCenter(TenantOwnedModel):
    """مراكز التكلفة لتوزيع وتحليل النفقات والإيرادات."""
    code = models.CharField("رمز مركز التكلفة", max_length=50)
    name = models.CharField("اسم مركز التكلفة", max_length=150)

    class Meta:
        verbose_name = "مركز تكلفة"
        verbose_name_plural = "مراكز التكلفة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="accounting_cost_center_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class JournalEntry(TenantOwnedModel):
    """رأس القيد اليومي المزدوج المعتمد."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        POSTED = "posted", "مرحل في دفتر الأستاذ"
        CANCELLED = "cancelled", "ملغى / معكوس"

    fiscal_period = models.ForeignKey(
        FiscalPeriod,
        verbose_name="الفترة المحاسبية",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    entry_number = models.CharField("رقم القيد اليومي", max_length=50, db_index=True)
    date = models.DateField("تاريخ القيد", default=timezone.localdate)
    description = models.TextField("شرح وبيان القيد المحاسبي")
    status = models.CharField("حالة القيد", max_length=20, choices=Status.choices, default=Status.DRAFT)
    posted_at = models.DateTimeField("تاريخ الترحيل", null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المحاسب المرحّل",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posted_journal_entries",
    )
    source_module = models.CharField("المصدر الآلي للقيد (رسوم، رواتب...)", max_length=50, blank=True)
    source_reference = models.CharField("رقم المعاملة المصدرية المرجعي", max_length=100, blank=True)

    class Meta:
        verbose_name = "قيد يومية"
        verbose_name_plural = "قيود اليومية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "entry_number"],
                condition=models.Q(is_archived=False),
                name="accounting_entry_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "date", "status"]),
        ]

    def __str__(self) -> str:
        return f"قيد #{self.entry_number} ({self.date}): {self.get_status_display()}"


class JournalEntryLine(TenantOwnedModel):
    """أسطر وأطراف القيد اليومي (المدين والدائن)."""
    journal_entry = models.ForeignKey(
        JournalEntry,
        verbose_name="القيد التابع له",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        verbose_name="الحساب المالي",
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        verbose_name="مركز التكلفة (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="journal_lines",
    )
    debit = models.DecimalField("مدين (Debit)", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField("دائن (Credit)", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    description = models.CharField("بيان السطر", max_length=255, blank=True)

    class Meta:
        verbose_name = "سطر قيد يومية"
        verbose_name_plural = "أسطر قيود اليومية"

    def __str__(self) -> str:
        return f"{self.account.name} | مدين: {self.debit} | دائن: {self.credit}"

    def clean(self):
        super().clean()
        if not self.account.is_leaf:
            raise ValidationError({"account": "لا يمكن الترحيل على حساب رئيسي تجميعي؛ يرجى اختيار حساب تفصيلي."})
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("لا يمكن أن يكون نفس السطر مديناً ودائناً في الوقت ذاته.")


# -----------------------------------------------------------------------------
# Expense Categories & Accounting Vouchers (سندات الصرف والقبض والمصروفات)
# -----------------------------------------------------------------------------

class ExpenseCategory(TenantOwnedModel):
    """تصنيفات المصروفات التشغيلية للمدرسة (إيجارات، فواتير، صيانة...)."""
    name = models.CharField("اسم تصنيف المصروف", max_length=150)
    code = models.CharField("رمز التصنيف", max_length=50)
    default_account = models.ForeignKey(
        Account,
        verbose_name="الحساب المحاسبي المرتبط في الدليل",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_categories",
    )
    description = models.TextField("وصف التصنيف", blank=True)

    class Meta:
        verbose_name = "تصنيف مصروفات"
        verbose_name_plural = "تصنيفات المصروفات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="accounting_exp_cat_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class PaymentVoucher(TenantOwnedModel):
    """سند صرف محاسبي للمصروفات، الإيجارات، وفواتير الموردين."""
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقداً (صندوق المدرسة)"
        BANK_TRANSFER = "bank_transfer", "تحويل بنكي"
        CHEQUE = "cheque", "شيك مصرفي"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        POSTED = "posted", "مرحل في القيود"
        CANCELLED = "cancelled", "ملغى"

    voucher_number = models.CharField("رقم سند الصرف", max_length=50, db_index=True)
    date = models.DateField("تاريخ الصرف", default=timezone.localdate)
    paid_to = models.CharField("صُرف إلى (المستفيد / الجهة)", max_length=200)
    amount = models.DecimalField("المبلغ المصروف", max_digits=14, decimal_places=2)
    payment_method = models.CharField("طريقة الدفع", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    credit_account = models.ForeignKey(
        Account,
        verbose_name="حساب الدفع (الصندوق أو البنك الدائن)",
        on_delete=models.PROTECT,
        related_name="credit_payment_vouchers",
    )
    debit_account = models.ForeignKey(
        Account,
        verbose_name="حساب النفقة (حساب المصروف المدين)",
        on_delete=models.PROTECT,
        related_name="debit_payment_vouchers",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        verbose_name="مركز التكلفة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_vouchers",
    )
    description = models.TextField("البيان وسبب الصرف")
    reference_number = models.CharField("رقم الشيك أو المرجع البنكي", max_length=100, blank=True)
    status = models.CharField("حالة السند", max_length=20, choices=Status.choices, default=Status.DRAFT)
    journal_entry = models.ForeignKey(
        JournalEntry,
        verbose_name="القيد اليومي المولد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_payment_vouchers",
    )

    class Meta:
        verbose_name = "سند صرف مالي"
        verbose_name_plural = "سندات الصرف المالي"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "voucher_number"],
                condition=models.Q(is_archived=False),
                name="accounting_pay_voucher_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"سند صرف #{self.voucher_number} - {self.paid_to}: {self.amount}"


class ReceiptVoucher(TenantOwnedModel):
    """سند قبض محاسبي عام للإيرادات المتنوعة بخلاف رسوم الطلاب (إيجار مرافق، تبرعات، أرباح...)."""
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقداً (صندوق المدرسة)"
        BANK_TRANSFER = "bank_transfer", "تحويل بنكي"
        CHEQUE = "cheque", "شيك مصرفي"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        POSTED = "posted", "مرحل في القيود"
        CANCELLED = "cancelled", "ملغى"

    voucher_number = models.CharField("رقم سند القبض العام", max_length=50, db_index=True)
    date = models.DateField("تاريخ القبض", default=timezone.localdate)
    received_from = models.CharField("قُبض من (الجهة / الشخص)", max_length=200)
    amount = models.DecimalField("المبلغ المقبوض", max_digits=14, decimal_places=2)
    payment_method = models.CharField("طريقة الاستلام", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    debit_account = models.ForeignKey(
        Account,
        verbose_name="حساب الاستلام (الصندوق أو البنك المدين)",
        on_delete=models.PROTECT,
        related_name="debit_receipt_vouchers",
    )
    credit_account = models.ForeignKey(
        Account,
        verbose_name="حساب الإيراد (الحساب الدائن)",
        on_delete=models.PROTECT,
        related_name="credit_receipt_vouchers",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        verbose_name="مركز التكلفة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receipt_vouchers",
    )
    description = models.TextField("البيان والغرض من القبض")
    reference_number = models.CharField("رقم الشيك أو المرجع البنكي", max_length=100, blank=True)
    status = models.CharField("حالة السند", max_length=20, choices=Status.choices, default=Status.DRAFT)
    journal_entry = models.ForeignKey(
        JournalEntry,
        verbose_name="القيد اليومي المولد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_receipt_vouchers",
    )

    class Meta:
        verbose_name = "سند قبض عام"
        verbose_name_plural = "سندات القبض العامة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "voucher_number"],
                condition=models.Q(is_archived=False),
                name="accounting_rec_voucher_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"سند قبض عام #{self.voucher_number} - {self.received_from}: {self.amount}"
