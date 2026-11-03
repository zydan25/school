"""Fixed assets administration with Unfold RTL support."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.assets.models import AssetCategory, AssetDepreciationEntry, AssetDisposal, AssetMovement, FixedAsset


@admin.register(AssetCategory)
class AssetCategoryAdmin(ModelAdmin):
    list_display = ("code", "name", "annual_depreciation_rate", "useful_life_years", "school")
    list_filter = ("school",)
    search_fields = ("code", "name")
    readonly_fields = ("asset_account", "depreciation_expense_account", "accumulated_depreciation_account")


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
    readonly_fields = ("id", "created_at", "updated_at", "asset", "fiscal_year", "depreciation_amount", "date", "journal_entry", "posted_at", "posted_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssetMovement)
class AssetMovementAdmin(ModelAdmin):
    list_display = ("asset", "movement_type", "from_branch", "to_branch", "movement_date", "recorded_by", "school")
    list_filter = ("school", "movement_type", "movement_date")
    search_fields = ("asset__code", "asset__name", "reason")
    readonly_fields = ("id", "school", "branch", "asset", "movement_type", "from_branch", "to_branch", "from_location", "to_location", "from_custodian", "to_custodian", "movement_date", "idempotency_key", "reason", "recorded_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssetDisposal)
class AssetDisposalAdmin(ModelAdmin):
    list_display = ("asset", "disposal_date", "proceeds", "journal_entry", "disposed_by", "school")
    list_filter = ("school", "disposal_date")
    search_fields = ("asset__code", "asset__name", "reason")
    readonly_fields = ("id", "school", "branch", "asset", "disposal_date", "proceeds", "payment_account", "journal_entry", "idempotency_key", "reason", "disposed_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
