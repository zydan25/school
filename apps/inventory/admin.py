"""Inventory and procurement administration with Unfold RTL support."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.inventory.models import (
    Supplier,
    Warehouse,
    InventoryItem,
    StockMovement,
    PurchaseOrder,
    PurchaseOrderItem,
)


@admin.register(Supplier)
class SupplierAdmin(ModelAdmin):
    list_display = ("code", "name", "contact_person", "phone", "email", "is_active", "school")
    list_filter = ("school", "is_active")
    search_fields = ("code", "name", "contact_person", "phone")


@admin.register(Warehouse)
class WarehouseAdmin(ModelAdmin):
    list_display = ("code", "name", "branch", "manager", "school")
    list_filter = ("school",)
    search_fields = ("code", "name", "location")
    raw_id_fields = ("manager", "branch")


@admin.register(InventoryItem)
class InventoryItemAdmin(ModelAdmin):
    list_display = ("code", "name", "warehouse", "category", "unit", "current_stock", "unit_cost", "reorder_level", "school")
    list_filter = ("school", "category", "warehouse")
    search_fields = ("code", "name", "category")
    raw_id_fields = ("warehouse",)


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = ("date", "movement_type", "item", "quantity", "unit_cost", "reference", "recipient_name", "school")
    list_filter = ("school", "movement_type", "date")
    search_fields = ("item__name", "item__code", "reference", "recipient_name")
    raw_id_fields = ("item",)


class PurchaseOrderItemInline(TabularInline):
    model = PurchaseOrderItem
    extra = 1
    raw_id_fields = ("item",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(ModelAdmin):
    list_display = ("order_number", "supplier", "warehouse", "order_date", "total_amount", "status", "school")
    list_filter = ("school", "status", "order_date")
    search_fields = ("order_number", "supplier__name")
    raw_id_fields = ("supplier", "warehouse", "approved_by")
    inlines = [PurchaseOrderItemInline]
