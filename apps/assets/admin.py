"""Fixed assets administration with Unfold RTL support."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.assets.models import AssetCategory, AssetDepreciationEntry, FixedAsset


@admin.register(AssetCategory)
class AssetCategoryAdmin(ModelAdmin):
    list_display = ("code", "name", "annual_depreciation_rate", "useful_life_years", "school")
    list_filter = ("school",)
    search_fields = ("code", "name")


class AssetDepreciationEntryInline(TabularInline):
    model = AssetDepreciationEntry
    extra = 0
    raw_id_fields = ("fiscal_year",)


@admin.register(FixedAsset)
class FixedAssetAdmin(ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "purchase_date",
        "purchase_cost",
        "accumulated_depreciation",
        "current_book_value",
        "status",
        "custodian",
        "school",
    )
    list_filter = ("school", "category", "status")
    search_fields = ("code", "name", "location_room")
    raw_id_fields = ("category", "custodian")
    inlines = [AssetDepreciationEntryInline]


@admin.register(AssetDepreciationEntry)
class AssetDepreciationEntryAdmin(ModelAdmin):
    list_display = ("asset", "fiscal_year", "depreciation_amount", "date", "school")
    list_filter = ("school", "fiscal_year")
    search_fields = ("asset__name", "asset__code")
    raw_id_fields = ("asset", "fiscal_year")
