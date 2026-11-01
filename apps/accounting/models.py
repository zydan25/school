"""Double-entry accounting, chart of accounts, and ledger domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TenantOwnedModel, TenantQuerySet


class FiscalYearQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        protected = {"is_closed", "closed_at", "closed_by", "closing_entry", "closing_entry_id", "opening_entry", "opening_entry_id", "start_date", "end_date", "school"}
        if protected.intersection(kwargs) and self.filter(is_closed=True).exists():
            raise ValidationError("لا يمكن تعديل بيانات سنة مالية مقفلة عبر QuerySet.update().")
        if protected.intersection(kwargs):
            raise ValidationError("تغيير حالة الإقفال أو تواريخ السنة المالية يجب أن يتم عبر خدمة الإقفال.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(is_closed=True).exists():
            raise ValidationError("لا يمكن حذف سنة مالية مقفلة.")
        return super().delete()


class FiscalYear(TenantOwnedModel):
    objects = FiscalYearQuerySet.as_manager()
    """السنة المالية المستقلة للمدرسة."""
    name = models.CharField("اسم السنة المالية", max_length=100)
    start_date = models.DateField("تاريخ بداية السنة المالية")
    end_date = models.DateField("تاريخ نهاية السنة المالية")
    is_closed = models.BooleanField("سنة مقفلة محاسبياً", default=False)
    closed_at = models.DateTimeField("تاريخ إقفال السنة", null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="closed_fiscal_years", verbose_name="المسؤول عن الإقفال")
    closing_entry = models.ForeignKey("JournalEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="closed_fiscal_years", verbose_name="قيد إقفال السنة")
    opening_entry = models.ForeignKey("JournalEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="opened_fiscal_years", verbose_name="قيد افتتاح السنة")

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

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "نهاية السنة المالية يجب ألا تسبق بدايتها."})
        if self.school_id and self.start_date and self.end_date:
            overlaps = FiscalYear.objects.filter(
                school_id=self.school_id, is_archived=False,
                start_date__lte=self.end_date, end_date__gte=self.start_date,
            ).exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError("تتداخل تواريخ السنة المالية مع سنة أخرى للمدرسة نفسها.")
        if self.is_closed and (not self.closed_at or not self.closed_by_id):
            raise ValidationError({"is_closed": "يجب تسجيل وقت الإقفال والمسؤول عنه قبل إقفال السنة المالية."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = FiscalYear.objects.filter(pk=self.pk).first()
            if original and original.is_closed:
                if not self.is_closed:
                    raise ValidationError("السنة المالية المقفلة لا يعاد فتحها بتعديل مباشر.")
                fields = ("school_id", "start_date", "end_date", "name")
                if any(getattr(original, field) != getattr(self, field) for field in fields):
                    raise ValidationError("لا يمكن تغيير بيانات سنة مالية مقفلة.")
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({'مقفلة' if self.is_closed else 'مفتوحة'})"


class FiscalPeriodQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        protected = {"is_closed", "closed_at", "closed_by", "start_date", "end_date", "fiscal_year", "fiscal_year_id", "period_number", "school"}
        if protected.intersection(kwargs) and self.filter(is_closed=True).exists():
            raise ValidationError("لا يمكن تعديل بيانات فترة مالية مقفلة عبر QuerySet.update().")
        if protected.intersection(kwargs):
            raise ValidationError("تغيير حالة الإقفال أو تواريخ الفترة يجب أن يتم عبر خدمة الإقفال.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(is_closed=True).exists():
            raise ValidationError("لا يمكن حذف فترة مالية مقفلة.")
        return super().delete()


class FiscalPeriod(TenantOwnedModel):
    objects = FiscalPeriodQuerySet.as_manager()
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
    closed_at = models.DateTimeField("تاريخ إقفال الفترة", null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="closed_fiscal_periods", verbose_name="المسؤول عن الإقفال")

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
            if self.period_number < 1 or self.period_number > 12:
                raise ValidationError({"period_number": "رقم الفترة يجب أن يكون بين 1 و12."})
            overlaps = FiscalPeriod.objects.filter(
                school_id=self.school_id, is_archived=False,
                start_date__lte=self.end_date, end_date__gte=self.start_date,
            ).exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError("تتداخل تواريخ الفترة مع فترة مالية أخرى للمدرسة نفسها.")
        if self.is_closed and (not self.closed_at or not self.closed_by_id):
            raise ValidationError({"closed_at": "تاريخ الإقفال والمسؤول عنه مطلوبان عند إقفال الفترة."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = FiscalPeriod.objects.filter(pk=self.pk).first()
            if original and original.is_closed:
                if not self.is_closed:
                    raise ValidationError("الفترة المالية المقفلة لا يعاد فتحها بتعديل مباشر.")
                fields = ("school_id", "fiscal_year_id", "period_number", "start_date", "end_date")
                if any(getattr(original, field) != getattr(self, field) for field in fields):
                    raise ValidationError("لا يمكن تغيير بيانات فترة مالية مقفلة.")
        return super().save(*args, **kwargs)


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

    def clean(self):
        super().clean()
        if self.parent_id:
            parent = self.parent
            if parent.school_id != self.school_id:
                raise ValidationError({"parent": "الحساب الأب لا يتبع المدرسة نفسها."})
            if parent.is_leaf:
                raise ValidationError({"parent": "لا يمكن إضافة حساب فرعي تحت حساب تفصيلي."})
            if parent.account_type != self.account_type:
                raise ValidationError({"account_type": "نوع الحساب يجب أن يطابق نوع الحساب الأب."})
            if parent.branch_id and parent.branch_id != self.branch_id:
                raise ValidationError({"parent": "الحساب الأب يتبع فرعاً مختلفاً."})
            ancestor = parent
            while ancestor:
                if self.pk and ancestor.pk == self.pk:
                    raise ValidationError({"parent": "لا يمكن إنشاء حلقة في شجرة الحسابات."})
                ancestor = ancestor.parent
        if self.is_leaf and self.pk and self.children.exists():
            raise ValidationError({"is_leaf": "لا يمكن تحويل حساب له حسابات فرعية إلى حساب تفصيلي."})
        if not self.is_leaf and self.pk and self.journal_lines.filter(journal_entry__status=JournalEntry.Status.POSTED).exists():
            raise ValidationError({"is_leaf": "لا يمكن تحويل حساب مستخدم في قيود مرحلة إلى حساب تجميعي."})

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

    def clean(self):
        super().clean()
        if self.branch_id and self.branch.school_id != self.school_id:
            raise ValidationError({"branch": "مركز التكلفة يجب أن يتبع المدرسة نفسها."})

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class JournalEntryQuerySet(models.QuerySet):
    """حماية دفتر الأستاذ العام من التعديل أو الحذف الجماعي للقيود المرحّلة."""
    def update(self, **kwargs):
        if self.filter(status="posted").exists():
            allowed = {"is_reversed", "reversed_by_entry", "reversed_by_entry_id", "reversal_reason", "updated_at"}
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
            models.Index(fields=["school", "source_module", "source_reference"]),
        ]

    def __str__(self) -> str:
        return f"قيد #{self.entry_number} ({self.date}): {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.status == self.Status.POSTED and not self.fiscal_period_id:
            raise ValidationError({"fiscal_period": "لا يمكن ترحيل قيد دون ربطه بفترة مالية."})
        if self.fiscal_period_id:
            if self.fiscal_period.school_id != self.school_id:
                raise ValidationError({"fiscal_period": "الفترة المحاسبية لا تتبع نفس المدرسة."})
            is_year_close_entry = (
                self.source_module == "fiscal_year_close"
                and self.source_reference == str(self.fiscal_period.fiscal_year_id)
                and self.date == self.fiscal_period.fiscal_year.end_date
            )
            if self.fiscal_period.is_closed and not is_year_close_entry:
                raise ValidationError({"fiscal_period": "لا يمكن الترحيل على فترة محاسبية مقفلة."})
            if self.fiscal_period.fiscal_year.is_closed:
                raise ValidationError({"fiscal_period": "السنة المالية التابعة لها هذه الفترة مقفلة."})
            if self.date < self.fiscal_period.start_date or self.date > self.fiscal_period.end_date:
                raise ValidationError({"date": "تاريخ القيد خارج حدود الفترة المالية."})

    def save(self, *args, **kwargs):
        if self.pk:
            orig = JournalEntry.objects.filter(pk=self.pk).first()
            if orig and orig.status == self.Status.POSTED:
                if self.status != self.Status.POSTED:
                    raise ValidationError("لا يمكن تحويل قيد محاسبي مرحّل إلى مسودة أو إلغاء ترحيله مباشرة؛ التصحيح يتم عبر قيد عكسي فقط.")
                allowed_fields = {"is_reversed", "reversed_by_entry", "reversed_by_entry_id", "reversal_reason", "updated_at"}
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
        """ترحيل ذري ومقفل للقيد بعد التحقق من الفترة والمصدر والمدين والدائن."""
        with transaction.atomic():
            locked = JournalEntry.objects.select_for_update().select_related(
                "fiscal_period__fiscal_year",
            ).get(pk=self.pk)
            if locked.status == self.Status.POSTED:
                raise ValidationError("القيد مرحّل مسبقاً.")
            from apps.tenants.models import School
            School.objects.select_for_update().get(pk=locked.school_id)
            if not locked.fiscal_period_id:
                raise ValidationError("لا يمكن ترحيل قيد دون فترة مالية مفتوحة.")
            period = FiscalPeriod.objects.select_for_update().select_related(
                "fiscal_year",
            ).get(pk=locked.fiscal_period_id)
            if period.school_id != locked.school_id:
                raise ValidationError("الفترة المالية لا تتبع مدرسة القيد.")
            if period.fiscal_year.is_closed:
                raise ValidationError("السنة المالية التابعة للفترة مقفلة.")
            is_year_close_entry = (
                locked.source_module == "fiscal_year_close"
                and locked.source_reference == str(period.fiscal_year_id)
                and locked.date == period.fiscal_year.end_date
                and period.is_closed
                and not period.fiscal_year.is_closed
            )
            if period.is_closed and not is_year_close_entry:
                raise ValidationError("لا يمكن الترحيل على فترة مالية مقفلة.")
            if locked.date < period.start_date or locked.date > period.end_date:
                raise ValidationError("تاريخ القيد يقع خارج حدود الفترة المالية المحددة.")

            if locked.source_module and locked.source_reference:
                duplicate_source = JournalEntry.objects.filter(
                    school_id=locked.school_id,
                    source_module=locked.source_module,
                    source_reference=locked.source_reference,
                    is_archived=False,
                ).exclude(pk=locked.pk).exists()
                if duplicate_source:
                    raise ValidationError("يوجد قيد آخر مسجل للمستند المصدر نفسه؛ يمنع تكرار الترحيل.")

            lines = list(
                JournalEntryLine.objects.select_for_update().filter(
                    journal_entry=locked, is_archived=False,
                ).select_related("account", "cost_center")
            )
            if not lines:
                raise ValidationError("لا يمكن ترحيل قيد محاسبي بدون أسطر تفصيلية.")
            total_debit = sum((line.debit for line in lines), Decimal("0.00"))
            total_credit = sum((line.credit for line in lines), Decimal("0.00"))
            if total_debit <= Decimal("0.00") or total_debit != total_credit:
                raise ValidationError(
                    f"القيد غير متوازن: إجمالي المدين ({total_debit}) لا يساوي إجمالي الدائن ({total_credit})."
                )
            for line in lines:
                if line.school_id != locked.school_id or line.account.school_id != locked.school_id:
                    raise ValidationError("يجب أن تتبع كافة أسطر القيد وحساباته مدرسة القيد نفسها.")
                if line.account.branch_id and line.branch_id != line.account.branch_id:
                    raise ValidationError("فرع سطر القيد لا يطابق فرع الحساب.")
                if locked.branch_id and line.branch_id and line.branch_id != locked.branch_id:
                    raise ValidationError("فرع سطر القيد لا يطابق فرع القيد.")
                if line.cost_center and line.cost_center.school_id != locked.school_id:
                    raise ValidationError("مركز التكلفة لا يتبع مدرسة القيد.")
                if line.cost_center and line.cost_center.branch_id and line.branch_id != line.cost_center.branch_id:
                    raise ValidationError("مركز التكلفة لا يتبع فرع سطر القيد.")
                if not line.account.is_leaf or line.account.is_archived:
                    raise ValidationError(f"الحساب '{line.account.name}' تجميعي أو مؤرشف ولا يقبل الترحيل.")
                if (
                    line.debit < Decimal("0.00")
                    or line.credit < Decimal("0.00")
                    or (line.debit == Decimal("0.00") and line.credit == Decimal("0.00"))
                    or (line.debit > Decimal("0.00") and line.credit > Decimal("0.00"))
                ):
                    raise ValidationError("كل سطر يجب أن يكون مديناً أو دائناً فقط وبقيمة موجبة.")

            locked.status = self.Status.POSTED
            locked.posted_at = timezone.now()
            locked.posted_by = user
            locked.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])
            self.status = locked.status
            self.posted_at = locked.posted_at
            self.posted_by = locked.posted_by
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
                        orig.journal_entry_id != self.journal_entry_id or
                        orig.description != self.description or
                        orig.branch_id != self.branch_id or
                        orig.school_id != self.school_id
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
    idempotency_key = models.CharField("مفتاح منع تكرار السند", max_length=100, blank=True, default="")
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
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False, idempotency_key__gt=""),
                name="acct_payment_idem_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "مبلغ سند الصرف يجب أن يكون أكبر من الصفر."})
        for account in (self.debit_account, self.credit_account):
            if account.school_id != self.school_id:
                raise ValidationError("حسابات سند الصرف يجب أن تتبع المدرسة نفسها.")
            if not account.is_leaf or account.is_archived:
                raise ValidationError("لا يمكن استخدام حساب تجميعي أو مؤرشف في سند الصرف.")
            if self.branch_id and account.branch_id and account.branch_id != self.branch_id:
                raise ValidationError("فرع حساب سند الصرف لا يطابق فرع السند.")
        if self.credit_account.account_type != Account.AccountType.ASSET:
            raise ValidationError({"credit_account": "حساب الصرف يجب أن يكون حساب أصول (صندوق أو بنك)."})
        if self.cost_center_id and self.cost_center.school_id != self.school_id:
            raise ValidationError({"cost_center": "مركز التكلفة لا يتبع المدرسة نفسها."})
        if self.idempotency_key and len(self.idempotency_key.strip()) < 8:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب ألا يقل عن 8 أحرف."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = PaymentVoucher.objects.filter(pk=self.pk).first()
            if original and original.status == self.Status.POSTED:
                protected = (
                    "school_id", "branch_id", "voucher_number", "date", "paid_to",
                    "amount", "payment_method", "credit_account_id", "debit_account_id",
                    "cost_center_id", "description", "reference_number", "idempotency_key",
                )
                if any(getattr(original, field) != getattr(self, field) for field in protected):
                    raise ValidationError("سند الصرف المرحّل غير قابل للتعديل؛ استخدم قيداً عكسياً.")
                if original.journal_entry_id and original.journal_entry_id != self.journal_entry_id:
                    raise ValidationError("لا يمكن تغيير القيد المرتبط بسند صرف مرحّل.")
                if self.status != self.Status.POSTED:
                    raise ValidationError("لا يمكن تغيير حالة سند صرف مرحّل مباشرة.")
        return super().save(*args, **kwargs)

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
    idempotency_key = models.CharField("مفتاح منع تكرار السند", max_length=100, blank=True)
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
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False, idempotency_key__gt=""),
                name="acct_receipt_idem_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "مبلغ سند القبض يجب أن يكون أكبر من الصفر."})
        for account in (self.debit_account, self.credit_account):
            if account.school_id != self.school_id:
                raise ValidationError("حسابات سند القبض يجب أن تتبع المدرسة نفسها.")
            if not account.is_leaf or account.is_archived:
                raise ValidationError("لا يمكن استخدام حساب تجميعي أو مؤرشف في سند القبض.")
            if self.branch_id and account.branch_id and account.branch_id != self.branch_id:
                raise ValidationError("فرع حساب سند القبض لا يطابق فرع السند.")
        if self.debit_account.account_type != Account.AccountType.ASSET:
            raise ValidationError({"debit_account": "حساب القبض يجب أن يكون حساب أصول (صندوق أو بنك)."})
        if self.cost_center_id and self.cost_center.school_id != self.school_id:
            raise ValidationError({"cost_center": "مركز التكلفة لا يتبع المدرسة نفسها."})
        if self.idempotency_key and len(self.idempotency_key.strip()) < 8:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب ألا يقل عن 8 أحرف."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = ReceiptVoucher.objects.filter(pk=self.pk).first()
            if original and original.status == self.Status.POSTED:
                protected = (
                    "school_id", "branch_id", "voucher_number", "date", "received_from",
                    "amount", "payment_method", "debit_account_id", "credit_account_id",
                    "cost_center_id", "description", "reference_number", "idempotency_key",
                )
                if any(getattr(original, field) != getattr(self, field) for field in protected):
                    raise ValidationError("سند القبض المرحّل غير قابل للتعديل؛ استخدم قيداً عكسياً.")
                if original.journal_entry_id and original.journal_entry_id != self.journal_entry_id:
                    raise ValidationError("لا يمكن تغيير القيد المرتبط بسند قبض مرحّل.")
                if self.status != self.Status.POSTED:
                    raise ValidationError("لا يمكن تغيير حالة سند قبض مرحّل مباشرة.")
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"سند قبض عام #{self.voucher_number} - {self.received_from}: {self.amount}"


class TreasuryAccount(TenantOwnedModel):
    """صندوق نقدي أو حساب بنكي مرتبط بحساب تفصيلي في دفتر الأستاذ."""
    class Kind(models.TextChoices):
        CASH = "cash", "صندوق نقدي"
        BANK = "bank", "حساب بنكي"

    name = models.CharField("اسم الصندوق أو الحساب البنكي", max_length=150)
    code = models.CharField("الرمز", max_length=50)
    kind = models.CharField("النوع", max_length=10, choices=Kind.choices)
    account = models.OneToOneField(
        Account,
        verbose_name="حساب الأستاذ المرتبط",
        on_delete=models.PROTECT,
        related_name="treasury_account",
    )
    bank_name = models.CharField("اسم البنك", max_length=150, blank=True)
    bank_account_number = models.CharField("رقم الحساب البنكي", max_length=100, blank=True)
    currency = models.CharField("رمز العملة", max_length=3, default="YER")
    is_default = models.BooleanField("الحساب الافتراضي لنوعه", default=False)
    is_active = models.BooleanField("نشط", default=True)

    class Meta:
        verbose_name = "صندوق / حساب بنكي"
        verbose_name_plural = "الصناديق والحسابات البنكية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="acct_treasury_code_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "kind", "is_active"], name="acct_tr_kind_active"),
        ]

    def clean(self):
        super().clean()
        if self.account_id:
            if self.account.school_id != self.school_id:
                raise ValidationError({"account": "حساب الأستاذ لا يتبع المدرسة نفسها."})
            if self.account.account_type != Account.AccountType.ASSET or not self.account.is_leaf:
                raise ValidationError({"account": "يجب ربط الصندوق أو البنك بحساب أصول تفصيلي."})
            if self.account.is_archived:
                raise ValidationError({"account": "لا يمكن ربط حساب أستاذ مؤرشف بالخزينة."})
            if self.account.branch_id and self.account.branch_id != self.branch_id:
                raise ValidationError({"account": "فرع حساب الأستاذ لا يطابق فرع الخزينة."})
        if self.kind == self.Kind.BANK and not self.bank_name.strip():
            raise ValidationError({"bank_name": "اسم البنك مطلوب للحساب البنكي."})
        if self.currency and len(self.currency) != 3:
            raise ValidationError({"currency": "رمز العملة يجب أن يتكون من ثلاثة أحرف."})

    def __str__(self):
        return f"{self.code} - {self.name}"


class TreasuryTransferQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        protected = {
            "school", "school_id", "branch", "branch_id", "transfer_number",
            "transfer_date", "source_account", "source_account_id",
            "destination_account", "destination_account_id", "amount",
            "idempotency_key", "journal_entry", "journal_entry_id", "status",
        }
        if protected.intersection(kwargs):
            raise ValidationError("تغيير التحويلات يتم عبر خدمات الخزينة الموثقة فقط.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status__in=["posted", "reversed"]).exists():
            raise ValidationError("لا يمكن حذف تحويل مرحّل أو معكوس؛ استخدم خدمة العكس.")
        return super().delete()


class TreasuryTransfer(TenantOwnedModel):
    objects = TreasuryTransferQuerySet.as_manager()
    """تحويل موثق بين صندوقين أو حسابين نقديين/بنكيين."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        POSTED = "posted", "مرحل"
        REVERSED = "reversed", "معكوس"

    transfer_number = models.CharField("رقم التحويل", max_length=60)
    transfer_date = models.DateField("تاريخ التحويل", default=timezone.localdate)
    source_account = models.ForeignKey(
        TreasuryAccount,
        verbose_name="من حساب",
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
    )
    destination_account = models.ForeignKey(
        TreasuryAccount,
        verbose_name="إلى حساب",
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
    )
    amount = models.DecimalField("مبلغ التحويل", max_digits=14, decimal_places=2)
    description = models.CharField("البيان", max_length=255)
    idempotency_key = models.CharField("مفتاح منع تكرار التحويل", max_length=100)
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.DRAFT)
    journal_entry = models.ForeignKey(
        JournalEntry,
        verbose_name="القيد المحاسبي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="treasury_transfers",
    )
    reversed_by_entry = models.ForeignKey(
        JournalEntry,
        verbose_name="القيد العكسي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_treasury_transfers",
    )

    class Meta:
        verbose_name = "تحويل خزينة"
        verbose_name_plural = "تحويلات الخزينة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "transfer_number"],
                condition=models.Q(is_archived=False),
                name="acct_transfer_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="acct_transfer_idem_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "مبلغ التحويل يجب أن يكون أكبر من الصفر."})
        if len(self.idempotency_key.strip()) < 8:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب ألا يقل عن 8 أحرف."})
        if self.source_account_id and self.destination_account_id:
            if self.source_account_id == self.destination_account_id:
                raise ValidationError("لا يمكن التحويل من الحساب إلى نفسه.")
            for treasury in (self.source_account, self.destination_account):
                if treasury.school_id != self.school_id:
                    raise ValidationError("حساب التحويل لا يتبع المدرسة نفسها.")
                if not treasury.is_active or treasury.is_archived:
                    raise ValidationError("لا يمكن استخدام حساب خزينة غير نشط أو مؤرشف.")
            if self.source_account.currency != self.destination_account.currency:
                raise ValidationError("لا يمكن تحويل مبالغ بين حسابين بعملتين مختلفتين دون عملية صرف مستقلة.")

    def save(self, *args, **kwargs):
        if self.pk:
            original = TreasuryTransfer.objects.filter(pk=self.pk).first()
            if original and original.status in (self.Status.POSTED, self.Status.REVERSED):
                protected = (
                    "school_id", "transfer_number", "transfer_date",
                    "source_account_id", "destination_account_id", "amount",
                    "description", "idempotency_key", "journal_entry_id",
                )
                if any(getattr(original, field) != getattr(self, field) for field in protected):
                    raise ValidationError("بيانات التحويل المرحّل غير قابلة للتعديل؛ صححها بقيد عكسي.")
                if original.status == self.Status.REVERSED and self.status != self.Status.REVERSED:
                    raise ValidationError("لا يمكن إعادة تحويل معكوس إلى حالة مرحّل.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transfer_number} - {self.amount}"


class BankReconciliationQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        protected = {
            "school", "school_id", "treasury_account", "treasury_account_id",
            "start_date", "end_date", "statement_opening_balance",
            "statement_closing_balance", "book_opening_balance",
            "book_closing_balance", "outstanding_ledger_amount", "difference",
            "status", "reconciled_at", "reconciled_by", "reconciled_by_id",
        }
        if protected.intersection(kwargs):
            raise ValidationError("تعديل المطابقة البنكية يتم عبر خدمة المطابقة فقط.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status="reconciled").exists():
            raise ValidationError("لا يمكن حذف مطابقة بنكية معتمدة.")
        return super().delete()


class BankReconciliation(TenantOwnedModel):
    objects = BankReconciliationQuerySet.as_manager()
    """محضر مطابقة كشف البنك مع دفتر الأستاذ لفترة محددة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        RECONCILED = "reconciled", "مطابق"

    treasury_account = models.ForeignKey(
        TreasuryAccount,
        verbose_name="الحساب البنكي",
        on_delete=models.PROTECT,
        related_name="reconciliations",
    )
    start_date = models.DateField("بداية كشف البنك")
    end_date = models.DateField("نهاية كشف البنك")
    statement_opening_balance = models.DecimalField("رصيد كشف البنك الافتتاحي", max_digits=14, decimal_places=2)
    statement_closing_balance = models.DecimalField("رصيد كشف البنك الختامي", max_digits=14, decimal_places=2)
    book_opening_balance = models.DecimalField("رصيد الأستاذ الافتتاحي", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    book_closing_balance = models.DecimalField("رصيد الأستاذ الختامي", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    outstanding_ledger_amount = models.DecimalField("حركات الأستاذ غير الظاهرة في الكشف", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    difference = models.DecimalField("فرق المطابقة", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.DRAFT)
    reconciled_at = models.DateTimeField("تاريخ المطابقة", null=True, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المسؤول عن المطابقة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_reconciliations",
    )

    class Meta:
        verbose_name = "مطابقة كشف بنكي"
        verbose_name_plural = "مطابقات كشوف البنوك"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "treasury_account", "start_date", "end_date"],
                condition=models.Q(is_archived=False),
                name="acct_bank_recon_range_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("بداية كشف البنك يجب ألا تتجاوز نهايته.")
        if self.treasury_account_id:
            if self.treasury_account.school_id != self.school_id:
                raise ValidationError({"treasury_account": "الحساب البنكي لا يتبع المدرسة نفسها."})
            if self.treasury_account.kind != TreasuryAccount.Kind.BANK:
                raise ValidationError({"treasury_account": "المطابقة البنكية تتطلب حساباً من نوع بنك."})
        if self.status == self.Status.RECONCILED and (
            not self.reconciled_at or not self.reconciled_by_id
        ):
            raise ValidationError({"reconciled_at": "وقت المطابقة والمسؤول عنها مطلوبان."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = BankReconciliation.objects.filter(pk=self.pk).first()
            if original and original.status == self.Status.RECONCILED:
                fields = (
                    "school_id", "treasury_account_id", "start_date", "end_date",
                    "statement_opening_balance", "statement_closing_balance",
                    "book_opening_balance", "book_closing_balance",
                    "outstanding_ledger_amount", "difference", "status",
                    "reconciled_at", "reconciled_by_id",
                )
                if any(getattr(original, field) != getattr(self, field) for field in fields):
                    raise ValidationError("المطابقة البنكية المعتمدة سجل مالي ثابت لا يقبل التعديل.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.RECONCILED:
            raise ValidationError("لا يمكن حذف مطابقة بنكية معتمدة.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.treasury_account} - {self.start_date} إلى {self.end_date}"


class BankStatementLineQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        if self.filter(reconciliation__status=BankReconciliation.Status.RECONCILED).exists():
            raise ValidationError("لا يمكن تعديل حركات كشف بنك بعد اعتماد المطابقة.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(reconciliation__status=BankReconciliation.Status.RECONCILED).exists():
            raise ValidationError("لا يمكن حذف حركات كشف بنك بعد اعتماد المطابقة.")
        return super().delete()


class BankStatementLine(TenantOwnedModel):
    objects = BankStatementLineQuerySet.as_manager()
    """حركة كشف بنك قابلة للربط بسطر محدد في دفتر الأستاذ."""
    reconciliation = models.ForeignKey(
        BankReconciliation,
        verbose_name="محضر المطابقة",
        on_delete=models.CASCADE,
        related_name="statement_lines",
    )
    transaction_date = models.DateField("تاريخ الحركة البنكية")
    external_reference = models.CharField("المرجع البنكي", max_length=120)
    description = models.CharField("البيان", max_length=255, blank=True)
    amount = models.DecimalField(
        "المبلغ (الإيداع موجب والسحب سالب)",
        max_digits=14,
        decimal_places=2,
    )
    journal_line = models.OneToOneField(
        JournalEntryLine,
        verbose_name="سطر دفتر الأستاذ المطابق",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_statement_match",
    )

    class Meta:
        verbose_name = "حركة كشف بنك"
        verbose_name_plural = "حركات كشوف البنوك"
        constraints = [
            models.UniqueConstraint(
                fields=["reconciliation", "external_reference"],
                condition=models.Q(is_archived=False),
                name="acct_bank_stmt_ref_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount == Decimal("0.00"):
            raise ValidationError({"amount": "قيمة حركة كشف البنك لا يمكن أن تكون صفراً."})
        if self.reconciliation_id:
            recon = self.reconciliation
            if recon.school_id != self.school_id:
                raise ValidationError({"reconciliation": "محضر المطابقة لا يتبع المدرسة نفسها."})
            if not (recon.start_date <= self.transaction_date <= recon.end_date):
                raise ValidationError({"transaction_date": "تاريخ الحركة خارج فترة كشف البنك."})
            if recon.status == BankReconciliation.Status.RECONCILED:
                raise ValidationError("لا يمكن إضافة أو تعديل حركة بعد اعتماد المطابقة.")
        if self.journal_line_id:
            line = self.journal_line
            if line.school_id != self.school_id:
                raise ValidationError({"journal_line": "سطر الأستاذ لا يتبع المدرسة نفسها."})
            if line.account_id != self.reconciliation.treasury_account.account_id:
                raise ValidationError({"journal_line": "سطر الأستاذ لا يخص الحساب البنكي المحدد."})
            if line.journal_entry.status != JournalEntry.Status.POSTED:
                raise ValidationError({"journal_line": "لا يمكن مطابقة حركة مع قيد غير مرحّل."})
            if line.journal_entry.date != self.transaction_date:
                raise ValidationError({"journal_line": "تاريخ سطر الأستاذ لا يطابق تاريخ الحركة البنكية."})
            if line.debit - line.credit != self.amount:
                raise ValidationError({"journal_line": "قيمة سطر الأستاذ لا تطابق قيمة حركة كشف البنك."})

    def delete(self, *args, **kwargs):
        if self.reconciliation.status == BankReconciliation.Status.RECONCILED:
            raise ValidationError("لا يمكن حذف حركة من مطابقة بنكية معتمدة.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.external_reference} - {self.amount}"
