"""Double-entry accounting, chart of accounts, and ledger domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
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

    def clean(self):
        super().clean()
        if self.fiscal_year_id and self.fiscal_year.school_id != self.school_id:
            raise ValidationError({"fiscal_year": "السنة المالية لا تتبع نفس المدرسة."})
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("تاريخ بداية الفترة لا يمكن أن يكون بعد تاريخ نهايتها.")
        if self.fiscal_year_id and self.start_date and self.end_date:
            if self.start_date < self.fiscal_year.start_date or self.end_date > self.fiscal_year.end_date:
                raise ValidationError("يجب أن تقع تواريخ الفترة المالية بالكامل داخل حدود السنة المالية التابعة لها.")


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


class JournalEntryQuerySet(models.QuerySet):
    """حماية دفتر الأستاذ العام من التعديل أو الحذف الجماعي للقيود المرحّلة."""
    def update(self, **kwargs):
        if self.filter(status="posted").exists():
            allowed = {"is_reversed", "reversed_by_entry", "reversed_by_entry_id", "reversal_reason", "updated_at", "is_archived"}
            disallowed = set(kwargs.keys()) - allowed
            if disallowed or ("status" in kwargs and kwargs["status"] != "posted"):
                raise ValidationError(f"لا يمكن تعديل القيود المحاسبية المرحّلة في دفتر الأستاذ عبر التحديث الجماعي QuerySet.update ({disallowed}).")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status="posted").exists():
            raise ValidationError("لا يمكن حذف قيود محاسبية مرحّلة في دفتر الأستاذ عبر الحذف الجماعي QuerySet.delete(). يرجى إنشاء قيود عكسية.")
        return super().delete()


class JournalEntry(TenantOwnedModel):
    """رأس القيد اليومي المزدوج المعتمد."""
    objects = JournalEntryQuerySet.as_manager()

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
    is_reversed = models.BooleanField("تم عكس القيد", default=False)
    reversed_by_entry = models.ForeignKey(
        "self",
        verbose_name="القيد العكسي المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reverses_entry",
    )
    reversal_reason = models.CharField("سبب العكس", max_length=255, blank=True)

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

    def clean(self):
        super().clean()
        if self.fiscal_period_id:
            if self.fiscal_period.school_id != self.school_id:
                raise ValidationError({"fiscal_period": "الفترة المحاسبية لا تتبع نفس المدرسة."})
            if self.fiscal_period.is_closed:
                raise ValidationError({"fiscal_period": "لا يمكن الترحيل على فترة محاسبية مقفلة."})
            if self.fiscal_period.fiscal_year.is_closed:
                raise ValidationError({"fiscal_period": "السنة المالية التابعة لها هذه الفترة مقفلة."})

    def save(self, *args, **kwargs):
        if self.pk:
            orig = JournalEntry.objects.filter(pk=self.pk).first()
            if orig and orig.status == self.Status.POSTED:
                if self.status != self.Status.POSTED:
                    raise ValidationError("لا يمكن تحويل قيد محاسبي مرحّل إلى مسودة أو إلغاء ترحيله مباشرة؛ التصحيح يتم عبر قيد عكسي فقط.")
                allowed_fields = {"is_reversed", "reversed_by_entry", "reversed_by_entry_id", "reversal_reason", "updated_at", "is_archived"}
                update_fields = kwargs.get("update_fields")
                if update_fields:
                    disallowed = set(update_fields) - allowed_fields
                    if disallowed:
                        raise ValidationError(f"لا يمكن تعديل الحقول {disallowed} في قيد محاسبي مرحّل.")
                else:
                    if (
                        orig.date != self.date or
                        orig.entry_number != self.entry_number or
                        orig.school_id != self.school_id or
                        orig.fiscal_period_id != self.fiscal_period_id or
                        orig.description != self.description or
                        orig.source_module != self.source_module or
                        orig.source_reference != self.source_reference
                    ):
                        raise ValidationError("القيد المحاسبي مرحّل ولا يمكن تعديل بياناته المالية أو بيانه مباشرة؛ التصحيح يتم عبر قيد عكسي.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.POSTED:
            raise ValidationError("لا يمكن حذف قيد محاسبي مرحّل نهائياً؛ يرجى إنشاء قيد عكسي لإلغاء أثره المالي.")
        return super().delete(*args, **kwargs)

    def post(self, user=None):
        """
        التحقق الصارم وترحيل القيد اليومي نهائياً إلى دفتر الأستاذ العام.
        يتحقق من توازن المدين والدائن، وتطابق المدرسة مع أسطر القيد وحسابات الدليل،
        وحالة الفترة المحاسبية.
        """
        if self.status == self.Status.POSTED:
            raise ValidationError("القيد مرحّل مسبقاً.")
        if self.fiscal_period and self.fiscal_period.is_closed:
            raise ValidationError("لا يمكن ترحيل القيد على فترة محاسبية مقفلة.")
        if self.fiscal_period and self.fiscal_period.fiscal_year.is_closed:
            raise ValidationError("السنة المالية التابعة لها هذه الفترة مقفلة.")
        if self.fiscal_period:
            if self.date < self.fiscal_period.start_date or self.date > self.fiscal_period.end_date:
                raise ValidationError(f"تاريخ القيد ({self.date}) يقع خارج حدود الفترة المحاسبية المحددة ({self.fiscal_period.start_date} إلى {self.fiscal_period.end_date}).")

        lines = list(self.lines.all())
        if not lines:
            raise ValidationError("لا يمكن ترحيل قيد محاسبي بدون أسطر تفصيلية.")
        total_debit = sum(line.debit for line in lines)
        total_credit = sum(line.credit for line in lines)
        if total_debit != total_credit:
            raise ValidationError(f"القيد غير متوازن: إجمالي المدين ({total_debit}) لا يساوي إجمالي الدائن ({total_credit}).")
        if total_debit <= Decimal("0.00"):
            raise ValidationError("يجب أن يحتوي القيد على مبالغ محاسبية أكبر من الصفر.")
        for line in lines:
            if line.school_id != self.school_id or line.account.school_id != self.school_id:
                raise ValidationError("عدم تطابق المدرسة: يجب أن تتبع كافة أسطر القيد وحساباتها نفس مدرسة القيد.")
            if not line.account.is_leaf:
                raise ValidationError(f"لا يمكن الترحيل على الحساب '{line.account.name}' لأنه حساب رئيسي تجميعي؛ يرجى اختيار حساب فرعي تفصيلي.")
            if line.account.is_archived:
                raise ValidationError(f"الحساب '{line.account.name}' معطل وموقوف عن العمليات.")
            if line.debit < Decimal("0.00") or line.credit < Decimal("0.00"):
                raise ValidationError("لا يمكن إدخال مبالغ سالبة في أسطر القيد المحاسبي.")
            if line.debit == Decimal("0.00") and line.credit == Decimal("0.00"):
                raise ValidationError("يجب إدخال مبلغ مدين أو دائن أكبر من الصفر في كل سطر من أسطر القيد.")
            if line.debit > Decimal("0.00") and line.credit > Decimal("0.00"):
                raise ValidationError("لا يمكن أن يكون السطر مديناً ودائناً في نفس الوقت.")
            if line.cost_center and line.cost_center.school_id != self.school_id:
                raise ValidationError("مركز التكلفة المحدد في سطر القيد لا يتبع نفس المدرسة.")

        self.status = self.Status.POSTED
        self.posted_at = timezone.now()
        if user:
            self.posted_by = user
        self.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])
        return self


class JournalEntryLineQuerySet(models.QuerySet):
    """حماية أسطر القيود في دفتر الأستاذ من التعديل أو الحذف الجماعي."""
    def update(self, **kwargs):
        if self.filter(journal_entry__status="posted").exists():
            raise ValidationError("لا يمكن تعديل أسطر قيود محاسبية مرحّلة في دفتر الأستاذ عبر التحديث الجماعي QuerySet.update().")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(journal_entry__status="posted").exists():
            raise ValidationError("لا يمكن حذف أسطر قيود محاسبية مرحّلة في دفتر الأستاذ عبر الحذف الجماعي QuerySet.delete().")
        return super().delete()


class JournalEntryLine(TenantOwnedModel):
    """أسطر وأطراف القيد اليومي (المدين والدائن)."""
    objects = JournalEntryLineQuerySet.as_manager()
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
        if self.journal_entry_id and self.journal_entry.school_id != self.school_id:
            raise ValidationError({"journal_entry": "القيد المحاسبي لا يتبع نفس المدرسة."})
        if self.account_id:
            if not self.account.is_leaf:
                raise ValidationError({"account": "لا يمكن الترحيل على حساب رئيسي تجميعي؛ يرجى اختيار حساب تفصيلي."})
            if self.account.school_id != self.school_id:
                raise ValidationError({"account": "الحساب المالي لا يتبع نفس المدرسة."})
        if self.cost_center_id and self.cost_center.school_id != self.school_id:
            raise ValidationError({"cost_center": "مركز التكلفة لا يتبع نفس المدرسة."})
        if self.debit < 0 or self.credit < 0:
            raise ValidationError("لا يمكن إدخال مبالغ سالبة في أسطر القيد المحاسبي.")
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("لا يمكن أن يكون نفس السطر مديناً ودائناً في الوقت ذاته.")
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("يجب إدخال مبلغ مدين أو دائن أكبر من الصفر في سطر القيد.")

    def save(self, *args, **kwargs):
        entry = self.journal_entry if hasattr(self, "journal_entry") else JournalEntry.objects.filter(pk=self.journal_entry_id).first()
        is_new = self._state.adding or not JournalEntryLine.objects.filter(pk=self.pk).exists()
        if entry:
            if is_new and entry.status == JournalEntry.Status.POSTED:
                raise ValidationError("لا يمكن إضافة سطر جديد إلى قيد محاسبي مرحّل نهائياً؛ التعديل يتم عبر قيد عكسي فقط.")
            if not is_new:
                orig = JournalEntryLine.objects.filter(pk=self.pk).select_related("journal_entry").first()
                if orig and orig.journal_entry and orig.journal_entry.status == JournalEntry.Status.POSTED:
                    if (
                        orig.account_id != self.account_id or
                        orig.debit != self.debit or
                        orig.credit != self.credit or
                        orig.cost_center_id != self.cost_center_id or
                        orig.journal_entry_id != self.journal_entry_id
                    ):
                        raise ValidationError("لا يمكن تعديل المبالغ أو الحسابات في سطر تابع لقيد محاسبي مرحّل.")
            if entry.school_id != self.school_id:
                raise ValidationError("القيد المحاسبي لا يتبع نفس مدرسة السطر المحاسبي.")

        if self.account_id and self.account.school_id != self.school_id:
            raise ValidationError("الحساب المالي لا يتبع نفس مدرسة السطر المحاسبي.")
        if self.cost_center_id and self.cost_center.school_id != self.school_id:
            raise ValidationError("مركز التكلفة لا يتبع نفس مدرسة السطر المحاسبي.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        entry = self.journal_entry if hasattr(self, "journal_entry") else JournalEntry.objects.filter(pk=self.journal_entry_id).first()
        if entry and entry.status == JournalEntry.Status.POSTED:
            raise ValidationError("لا يمكن حذف سطر من قيد محاسبي مرحّل.")
        return super().delete(*args, **kwargs)


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
