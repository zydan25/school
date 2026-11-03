"""Administration for optional school transportation, library, and book services."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.school_services.models import (
    BookLoan,
    BookRequisitionFulfillment,
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusRoute,
    BusSubscriptionCharge,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
)


@admin.register(BusRoute)
class BusRouteAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "route_code", "route_name", "bus_number", "driver_name", "driver_phone",
        "bus_capacity", "compensation_type", "contract_amount", "contractor_type",
        "monthly_fee", "is_active", "school",
    )
    list_filter = ("school", "is_active", "compensation_type", "contractor_type")
    search_fields = ("route_code", "route_name", "bus_number", "driver_name", "driver_phone", "destination_area")


    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(StudentBusSubscription)
class StudentBusSubscriptionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "bus_route", "academic_year", "subscription_type", "status", "school")
    list_filter = ("school", "status", "subscription_type", "academic_year")
    search_fields = ("student__user__first_name", "student__user__last_name", "bus_route__route_name")
    raw_id_fields = ("student", "bus_route", "academic_year", "school", "branch")


    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(BusSubscriptionCharge)
class BusSubscriptionChargeAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("subscription", "invoice", "billing_year", "billing_month", "amount", "issued_by", "school")
    list_filter = ("school", "billing_year", "billing_month")
    search_fields = ("invoice__invoice_number", "subscription__student__first_name", "subscription__student__last_name")
    raw_id_fields = ("subscription", "invoice", "issued_by", "school", "branch")
    readonly_fields = ("id", "subscription", "invoice", "billing_year", "billing_month", "amount", "issued_by", "created_at", "updated_at", "school", "branch", "is_archived", "archived_at", "archived_by", "archive_reason")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS") and super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BusFinancialSettlement)
class BusFinancialSettlementAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "bus_route", "month", "year", "student_count", "rate_applied",
        "gross_due", "advances_withdrawn", "net_payable", "status", "school",
    )
    list_filter = ("school", "status", "year", "month")
    search_fields = ("bus_route__bus_number", "bus_route__driver_name", "notes")
    raw_id_fields = ("bus_route", "academic_year", "approved_by", "payment_voucher", "school", "branch")
    readonly_fields = ("student_count", "rate_applied", "gross_due", "net_payable", "status", "approved_by", "payment_voucher")


    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(LibraryBook)
class LibraryBookAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("isbn", "title", "author", "category", "total_copies", "available_copies", "shelf_location", "school")
    list_filter = ("school", "category")
    search_fields = ("isbn", "title", "author", "publisher")
    readonly_fields = ("total_copies", "available_copies")


    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(BookLoan)
class BookLoanAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "book", "student", "teacher", "borrow_date", "due_date",
        "return_date", "status", "fine_amount", "renewal_count", "school",
    )
    list_filter = ("school", "status", "borrow_date")
    search_fields = ("book__title", "student__user__first_name", "teacher__user__first_name")
    raw_id_fields = ("book", "student", "teacher", "fine_invoice", "school", "branch")
    readonly_fields = ("status", "return_date", "fine_amount", "fine_invoice", "renewal_count")


    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(StudentBookDistribution)
class StudentBookDistributionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "student", "book_title", "quantity", "fee_amount", "delivery_status",
        "delivered_at", "delivered_by", "returned_at", "returned_by", "school",
    )
    list_filter = ("school", "delivery_status", "academic_year")
    search_fields = ("student__first_name", "student__last_name", "book_title")
    raw_id_fields = ("student", "academic_year", "delivered_by", "returned_by", "invoice", "inventory_item", "school", "branch")
    readonly_fields = ("delivery_status", "delivered_at", "delivered_by", "returned_at", "returned_by", "invoice")
    actions = ("deliver_selected_books", "return_selected_books")

    @admin.action(description="تسليم الكتب المحددة للطلاب وخصمها من المستودع")
    def deliver_selected_books(self, request, queryset):
        success = 0
        for distribution in queryset.select_related("inventory_item", "student"):
            if distribution.delivery_status == distribution.DeliveryStatus.PENDING:
                distribution.deliver_book(user=request.user)
                success += 1
        self.message_user(request, f"تم تسليم {success} سجل كتاب وتحديث أرصدة المخزون.")

    @admin.action(description="استرجاع الكتب المحددة إلى المستودع")
    def return_selected_books(self, request, queryset):
        success = 0
        for distribution in queryset.select_related("inventory_item", "student"):
            if distribution.delivery_status == distribution.DeliveryStatus.DELIVERED:
                distribution.return_book(user=request.user)
                success += 1
        self.message_user(request, f"تم استرجاع {success} سجل كتاب وإعادتها للمستودع.")


    def has_delete_permission(self, request, obj=None):
        return False

class BookRequisitionItemInline(TabularInline):
    model = BookRequisitionItem
    extra = 1
    fields = ("book_title", "quantity_requested", "quantity_approved", "quantity_dispatched", "notes")
    readonly_fields = ("quantity_approved", "quantity_dispatched")

    def has_add_permission(self, request, obj=None):
        return obj is None or obj.status == BookRequisitionOrder.Status.DRAFT

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.status == BookRequisitionOrder.Status.DRAFT


@admin.register(BookRequisitionOrder)
class BookRequisitionOrderAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "order_number", "requested_by", "academic_year", "grade_level", "section",
        "status", "approved_by", "fulfilled_by", "created_at", "school",
    )
    list_filter = ("school", "status", "academic_year")
    search_fields = ("order_number", "requested_by__phone", "requested_by__first_name", "requested_by__last_name", "notes")
    raw_id_fields = ("requested_by", "approved_by", "fulfilled_by", "academic_year", "grade_level", "section", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at", "status", "approved_by", "approved_at", "fulfilled_by", "fulfilled_at")
    inlines = (BookRequisitionItemInline,)


    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(BookRequisitionFulfillment)
class BookRequisitionFulfillmentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("requisition", "idempotency_key", "line_count", "created_by", "created_at", "school")
    list_filter = ("school", "created_at")
    search_fields = ("requisition__order_number", "idempotency_key")
    raw_id_fields = ("requisition", "created_by", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at", "requisition", "idempotency_key", "payload_hash", "line_count", "created_by", "school", "branch", "is_archived", "archived_at", "archived_by", "archive_reason")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS") and super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BookRequisitionItem)
class BookRequisitionItemAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("requisition", "book_title", "quantity_requested", "quantity_approved", "quantity_dispatched", "school")
    list_filter = ("school",)
    search_fields = ("book_title", "requisition__order_number")
    raw_id_fields = ("requisition", "school", "branch")
    readonly_fields = ("quantity_approved", "quantity_dispatched")


    def has_delete_permission(self, request, obj=None):
        if obj is None or obj.requisition.status != BookRequisitionOrder.Status.DRAFT:
            return False
        return super().has_delete_permission(request, obj)
