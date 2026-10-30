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

    class Meta:
        verbose_name = "تصنيف أصول"
        verbose_name_plural = "تصنيفات الأصول الثابتة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="assets_category_code_uniq",
            )
        ]

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
        if self.asset_id:
            depreciable_base = max(Decimal("0.00"), self.asset.purchase_cost - self.asset.salvage_value)
            max_allowed = max(Decimal("0.00"), depreciable_base - self.asset.accumulated_depreciation)
            if self._state.adding and self.depreciation_amount > max_allowed:
                raise ValidationError({
                    "depreciation_amount": f"مبلغ الإهلاك ({self.depreciation_amount}) يتجاوز القيمة القابلة للإهلاك المتبقية ({max_allowed})."
                })
