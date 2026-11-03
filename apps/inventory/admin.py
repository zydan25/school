"""Inventory and procurement administration with Unfold RTL support."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.inventory.models import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    StockMovement,
    Supplier,
    VendorInvoice,
    VendorInvoicePayment,
    Warehouse,
    WarehouseStock,
    WarehouseTransfer,
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
    readonly_fields = ("current_stock", "unit_cost")


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = ("date", "movement_type", "item", "quantity", "unit_cost", "reference", "recipient_name", "school")
    list_filter = ("school", "movement_type", "date")
    search_fields = ("item__name", "item__code", "reference", "recipient_name")
    raw_id_fields = ("item", "warehouse")
    readonly_fields = ("id", "school", "branch", "item", "warehouse", "movement_type", "quantity", "unit_cost", "date", "reference", "recipient_name", "notes", "idempotency_key", "created_by", "purchase_order_item", "purchase_receipt", "transfer", "reversal_of", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    readonly_fields = ("total_amount", "status", "approved_by", "approved_at", "received_at")
    inlines = [PurchaseOrderItemInline]


@admin.register(VendorInvoice)
class VendorInvoiceAdmin(ModelAdmin):
    list_display = (
        "invoice_number",
        "supplier",
        "purchase_order",
        "invoice_date",
        "due_date",
        "total_amount",
        "paid_amount",
        "remaining_amount_display",
        "status",
        "journal_entry",
        "school",
    )
    list_filter = ("school", "status", "invoice_date")
    search_fields = ("invoice_number", "supplier__name", "supplier__code")
    raw_id_fields = ("supplier", "purchase_order", "journal_entry", "expense_account", "cost_center")
    readonly_fields = ("paid_amount", "status", "approved_by", "approved_at", "journal_entry")
    actions = ["post_selected_invoices_to_journal"]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="المبلغ المتبقي")
    def remaining_amount_display(self, obj):
        return obj.remaining_amount

    @admin.action(description="ترحيل الفواتير المحددة إلى قيود استحقاق محاسبية")
    def post_selected_invoices_to_journal(self, request, queryset):
        from django.core.exceptions import ValidationError
        from apps.inventory.services import approve_vendor_invoice

        posted_count = 0
        errors = []
        for invoice in queryset:
            try:
                approve_vendor_invoice(invoice=invoice, approved_by=request.user)
                posted_count += 1
            except ValidationError as exc:
                errors.append(f"{invoice.invoice_number}: {'; '.join(exc.messages)}")
        if posted_count:
            self.message_user(request, f"تم اعتماد وترحيل {posted_count} فاتورة مورد بنجاح.")
        for error in errors[:10]:
            self.message_user(request, error, level="ERROR")



@admin.register(WarehouseStock)
class WarehouseStockAdmin(ModelAdmin):
    list_display = ("item", "warehouse", "quantity", "average_unit_cost", "school")
    list_filter = ("school", "warehouse")
    search_fields = ("item__code", "item__name", "warehouse__name")
    readonly_fields = ("id", "school", "branch", "item", "warehouse", "quantity", "average_unit_cost", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PurchaseReceipt)
class PurchaseReceiptAdmin(ModelAdmin):
    list_display = ("receipt_number", "purchase_order", "received_at", "received_by", "school")
    list_filter = ("school", "received_at")
    search_fields = ("receipt_number", "purchase_order__order_number")
    readonly_fields = ("id", "school", "branch", "purchase_order", "receipt_number", "idempotency_key", "payload_hash", "received_at", "received_by", "notes", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WarehouseTransfer)
class WarehouseTransferAdmin(ModelAdmin):
    list_display = ("transfer_number", "item", "source_warehouse", "destination_warehouse", "quantity", "status", "school")
    list_filter = ("school", "status", "transfer_date")
    search_fields = ("transfer_number", "item__code", "item__name")
    readonly_fields = ("id", "school", "branch", "transfer_number", "item", "source_warehouse", "destination_warehouse", "quantity", "unit_cost", "transfer_date", "idempotency_key", "status", "posted_by", "posted_at", "reversed_at", "notes", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VendorInvoicePayment)
class VendorInvoicePaymentAdmin(ModelAdmin):
    list_display = ("invoice", "payment_voucher", "amount", "payment_date", "recorded_by", "school")
    list_filter = ("school", "payment_date")
    search_fields = ("invoice__invoice_number", "payment_voucher__voucher_number")
    readonly_fields = ("id", "school", "branch", "invoice", "payment_voucher", "journal_entry", "amount", "idempotency_key", "payment_date", "recorded_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
