"""Fixed assets, categories, and depreciation models."""
from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class AssetCategory(TenantOwnedModel):
    """تصنيفات الأصول الثابتة (أجهزة حاسوب، مباني، حافلات، أثاث)."""
    name = models.CharField("اسم تصنيف الأصول", max_length=150)
    code = models.CharField("رمز التصنيف", max_length=50)
    annual_depreciation_rate = models.DecimalField("نسبة الإهلاك السنوي (%)", max_digits=5, decimal_places=2, default=Decimal("10.00"))
    useful_life_years = models.PositiveSmallIntegerField("العمر الإنتاجي التقديري بالسنوات", default=5)
    asset_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_categories", verbose_name="حساب تكلفة الأصل",
    )
    depreciation_expense_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_categories_expense", verbose_name="حساب مصروف الإهلاك",
    )
    accumulated_depreciation_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_categories_accumulated", verbose_name="حساب مجمع الإهلاك",
    )

    class Meta:
        verbose_name = "تصنيف أصول"
        verbose_name_plural = "تصنيفات الأصول الثابتة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="assets_category_code_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(annual_depreciation_rate__gte=0) & models.Q(annual_depreciation_rate__lte=100),
                name="assets_category_rate_range",
            ),
            models.CheckConstraint(
                condition=models.Q(useful_life_years__gt=0),
                name="assets_category_life_positive",
            ),
        ]

    def clean(self):
        super().clean()
        for field in ("asset_account", "depreciation_expense_account", "accumulated_depreciation_account"):
            account = getattr(self, field)
            if account and account.school_id != self.school_id:
                raise ValidationError({field: "الحساب المالي لا يتبع المدرسة نفسها."})
        if not Decimal("0.00") <= self.annual_depreciation_rate <= Decimal("100.00"):
            raise ValidationError({"annual_depreciation_rate": "نسبة الإهلاك يجب أن تكون بين صفر و100 بالمئة."})
        if self.useful_life_years <= 0:
            raise ValidationError({"useful_life_years": "العمر الإنتاجي يجب أن يكون أكبر من صفر."})

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class FixedAsset(TenantOwnedModel):
    """سجل الأصل الثابت وتفاصيله وموقعه وإهلاكه."""
    class Status(models.TextChoices):
        ACTIVE = "active", "يعمل بحالة ممتازة"
        IN_MAINTENANCE = "in_maintenance", "تحت الصيانة والإصلاح"
        DISPOSED = "disposed", "مستبعد / تالف"

    category = models.ForeignKey(
        AssetCategory,
        verbose_name="تصنيف الأصل",
        on_delete=models.PROTECT,
        related_name="assets",
    )
    code = models.CharField("رمز / باركود الأصل", max_length=50, db_index=True)
    name = models.CharField("اسم ووصف الأصل", max_length=200)
    purchase_date = models.DateField("تاريخ الشراء / التملك")
    purchase_cost = models.DecimalField("تكلفة الشراء الأصلية", max_digits=14, decimal_places=2)
    salvage_value = models.DecimalField("القيمة التخريدية المتوقعة", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    location_room = models.CharField("موقع الأصل (المبنى / القاعة)", max_length=150, blank=True)
    custodian = models.ForeignKey(
        "staff.Teacher",
        verbose_name="الموظف / المعلم المسؤول عن العهدة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="custody_assets",
    )
    accumulated_depreciation = models.DecimalField("مجمع الإهلاك المتراكم", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة الأصل", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    source_vendor_invoice = models.ForeignKey(
        "inventory.VendorInvoice", null=True, blank=True, on_delete=models.PROTECT,
        related_name="capitalized_assets", verbose_name="فاتورة المورد المصدر",
    )
    acquisition_journal_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.PROTECT,
        related_name="acquired_fixed_assets", verbose_name="قيد اقتناء الأصل",
    )
    disposal_journal_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.PROTECT,
        related_name="disposed_fixed_assets", verbose_name="قيد استبعاد الأصل",
    )
    disposed_at = models.DateTimeField("تاريخ استبعاد الأصل", null=True, blank=True)

    class Meta:
        verbose_name = "أصل ثابت"
        verbose_name_plural = "الأصول الثابتة والعهد"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="assets_fixed_asset_code_uniq",
            )
        ]

    def clean(self):
        super().clean()
        if self.category_id and self.category.school_id != self.school_id:
            raise ValidationError({"category": "تصنيف الأصل لا يتبع المدرسة نفسها."})
        if self.custodian_id and self.custodian.school_id != self.school_id:
            raise ValidationError({"custodian": "مسؤول العهدة لا يتبع المدرسة نفسها."})
        if self.purchase_cost <= 0:
            raise ValidationError({"purchase_cost": "تكلفة الأصل يجب أن تكون أكبر من صفر."})
        if self.salvage_value < 0 or self.salvage_value > self.purchase_cost:
            raise ValidationError({"salvage_value": "القيمة التخريدية يجب أن تكون بين صفر وتكلفة الشراء."})
        if self.accumulated_depreciation < 0 or self.accumulated_depreciation > self.purchase_cost - self.salvage_value:
            raise ValidationError({"accumulated_depreciation": "مجمع الإهلاك يتجاوز القيمة القابلة للإهلاك."})
        if self.source_vendor_invoice_id:
            invoice = self.source_vendor_invoice
            if invoice.school_id != self.school_id:
                raise ValidationError({"source_vendor_invoice": "فاتورة المورد لا تتبع المدرسة نفسها."})
            if invoice.accounting_treatment != "fixed_asset":
                raise ValidationError({"source_vendor_invoice": "فاتورة المورد ليست مصنفة كاقتناء أصل ثابت."})
        for field in ("acquisition_journal_entry", "disposal_journal_entry"):
            entry = getattr(self, field)
            if entry and entry.school_id != self.school_id:
                raise ValidationError({field: "القيد المحاسبي لا يتبع المدرسة نفسها."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = FixedAsset.objects.filter(pk=self.pk).first()
            if original:
                protected = ("category_id", "purchase_date", "purchase_cost", "salvage_value", "source_vendor_invoice_id")
                if any(getattr(original, field) != getattr(self, field) for field in protected):
                    raise ValidationError("بيانات اقتناء الأصل التاريخية لا تعدل؛ استخدم مستند تسوية معتمداً.")
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"[{self.code}] {self.name} - {self.current_book_value}"

    @property
    def current_book_value(self) -> Decimal:
        return max(Decimal("0.00"), self.purchase_cost - self.accumulated_depreciation)


class AssetDepreciationEntry(TenantOwnedModel):
    """سجلات الإهلاك الدوري للأصل وربطها بالسنوات المالية."""
    asset = models.ForeignKey(
        FixedAsset,
        verbose_name="الأصل الثابت",
        on_delete=models.CASCADE,
        related_name="depreciations",
    )
    fiscal_year = models.ForeignKey(
        "accounting.FiscalYear",
        verbose_name="السنة المالية",
        on_delete=models.PROTECT,
        related_name="asset_depreciations",
    )
    depreciation_amount = models.DecimalField("قسط إهلاك الفترة", max_digits=14, decimal_places=2)
    date = models.DateField("تاريخ قيد الإهلاك", default=timezone.localdate)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_depreciation_entries", verbose_name="قيد الإهلاك المرحّل",
    )
    posted_at = models.DateTimeField("تاريخ ترحيل الإهلاك", null=True, blank=True)
    posted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posted_asset_depreciations", verbose_name="مرحل الإهلاك",
    )

    class Meta:
        verbose_name = "قيد إهلاك أصل"
        verbose_name_plural = "سجلات إهلاك الأصول"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "asset", "fiscal_year"],
                condition=models.Q(is_archived=False),
                name="assets_depreciation_asset_year_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.asset.name} - {self.fiscal_year.name}: {self.depreciation_amount}"

    def clean(self):
        super().clean()
        if self.asset_id and self.asset.school_id != self.school_id:
            raise ValidationError({"asset": "الأصل لا يتبع نفس المدرسة."})
        if self.fiscal_year_id and self.fiscal_year.school_id != self.school_id:
            raise ValidationError({"fiscal_year": "السنة المالية لا تتبع نفس المدرسة."})
        if self.journal_entry_id and self.journal_entry.school_id != self.school_id:
            raise ValidationError({"journal_entry": "قيد الإهلاك لا يتبع المدرسة نفسها."})
        if self.depreciation_amount <= 0:
            raise ValidationError({"depreciation_amount": "قسط الإهلاك يجب أن يكون أكبر من صفر."})
        if self.fiscal_year_id and self.date and not (
            self.fiscal_year.start_date <= self.date <= self.fiscal_year.end_date
        ):
            raise ValidationError({"date": "تاريخ الإهلاك خارج حدود السنة المالية."})
        if self.asset_id:
            depreciable_base = max(Decimal("0.00"), self.asset.purchase_cost - self.asset.salvage_value)
            max_allowed = max(Decimal("0.00"), depreciable_base - self.asset.accumulated_depreciation)
            if self._state.adding and self.depreciation_amount > max_allowed:
                raise ValidationError({
                    "depreciation_amount": f"مبلغ الإهلاك ({self.depreciation_amount}) يتجاوز القيمة القابلة للإهلاك المتبقية ({max_allowed})."
                })


class AssetMovement(TenantOwnedModel):
    """سجل تاريخي لنقل الأصل أو تغيير عهدته وموقعه."""
    class MovementType(models.TextChoices):
        TRANSFER = "transfer", "نقل بين الفروع أو المواقع"
        CUSTODY = "custody", "تسليم أو استلام عهدة"

    asset = models.ForeignKey(
        FixedAsset, on_delete=models.PROTECT, related_name="movements",
        verbose_name="الأصل",
    )
    movement_type = models.CharField("نوع الحركة", max_length=20, choices=MovementType.choices)
    from_branch = models.ForeignKey(
        "tenants.Branch", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_movements_from", verbose_name="الفرع السابق",
    )
    to_branch = models.ForeignKey(
        "tenants.Branch", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_movements_to", verbose_name="الفرع الجديد",
    )
    from_location = models.CharField("الموقع السابق", max_length=150, blank=True)
    to_location = models.CharField("الموقع الجديد", max_length=150, blank=True)
    from_custodian = models.ForeignKey(
        "staff.Teacher", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_custody_out", verbose_name="أمين العهدة السابق",
    )
    to_custodian = models.ForeignKey(
        "staff.Teacher", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_custody_in", verbose_name="أمين العهدة الجديد",
    )
    movement_date = models.DateField("تاريخ الحركة", default=timezone.localdate)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=100)
    reason = models.CharField("سبب النقل أو تغيير العهدة", max_length=500)
    recorded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="asset_movements_recorded", verbose_name="مسجل الحركة",
    )

    class Meta:
        verbose_name = "حركة نقل أصل أو عهدة"
        verbose_name_plural = "سجل نقل الأصول والعهد"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="assets_movement_idem_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.asset_id and self.asset.school_id != self.school_id:
            raise ValidationError({"asset": "الأصل لا يتبع المدرسة نفسها."})
        for field in ("from_branch", "to_branch", "from_custodian", "to_custodian"):
            obj = getattr(self, field)
            if obj and obj.school_id != self.school_id:
                raise ValidationError({field: "الفرع أو أمين العهدة لا يتبع المدرسة نفسها."})
        if len(self.idempotency_key.strip()) < 8:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب ألا يقل عن 8 أحرف."})
        if not self.reason.strip():
            raise ValidationError({"reason": "سبب النقل أو تغيير العهدة مطلوب."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("سجل حركة الأصل تاريخي وغير قابل للتعديل.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يجوز حذف سجل نقل أصل أو عهدة.")


class AssetDisposal(TenantOwnedModel):
    """مستند استبعاد أصل مع تسوية القيمة الدفترية وربطه بالقيد المحاسبي."""
    asset = models.OneToOneField(
        FixedAsset, on_delete=models.PROTECT, related_name="disposal",
        verbose_name="الأصل المستبعد",
    )
    disposal_date = models.DateField("تاريخ الاستبعاد", default=timezone.localdate)
    proceeds = models.DecimalField("قيمة البيع أو المتحصل", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    payment_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_disposals", verbose_name="حساب تحصيل قيمة البيع",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_disposals", verbose_name="قيد الاستبعاد",
    )
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=100)
    reason = models.CharField("سبب الاستبعاد", max_length=500)
    disposed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="asset_disposals", verbose_name="منفذ الاستبعاد",
    )
    created_at = models.DateTimeField("تاريخ الإنشاء", default=timezone.now)

    class Meta:
        verbose_name = "مستند استبعاد أصل"
        verbose_name_plural = "مستندات استبعاد الأصول"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="assets_disposal_idem_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(proceeds__gte=0),
                name="assets_disposal_proceeds_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.asset_id and self.asset.school_id != self.school_id:
            raise ValidationError({"asset": "الأصل لا يتبع المدرسة نفسها."})
        if self.payment_account_id and self.payment_account.school_id != self.school_id:
            raise ValidationError({"payment_account": "حساب التحصيل لا يتبع المدرسة نفسها."})
        if self.journal_entry_id and self.journal_entry.school_id != self.school_id:
            raise ValidationError({"journal_entry": "قيد الاستبعاد لا يتبع المدرسة نفسها."})
        if self.proceeds < 0 or len(self.idempotency_key.strip()) < 8:
            raise ValidationError("قيمة المتحصل غير سالبة ومفتاح منع التكرار بطول 8 أحرف مطلوب.")
        if not self.reason.strip():
            raise ValidationError({"reason": "سبب الاستبعاد مطلوب."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("مستند استبعاد الأصل غير قابل للتعديل.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يجوز حذف مستند استبعاد أصل؛ التصحيح بالقيد العكسي الموثق.")
