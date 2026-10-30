"""School support services administration with Unfold RTL support."""
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.school_services.models import (
    BookLoan,
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusRoute,
    ClinicVisit,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
    StudentHealthProfile,
)


@admin.register(BusRoute)
class BusRouteAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("route_code", "route_name", "bus_number", "driver_name", "driver_phone", "compensation_type", "contract_amount", "contractor_type", "monthly_fee", "is_active", "school")
    list_filter = ("school", "is_active", "compensation_type", "contractor_type")
    search_fields = ("route_code", "route_name", "bus_number", "driver_name", "driver_phone", "destination_area")


@admin.register(BusFinancialSettlement)
class BusFinancialSettlementAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("bus_route", "month", "year", "student_count", "rate_applied", "gross_due", "advances_withdrawn", "net_payable", "status", "school")
    list_filter = ("school", "status", "year", "month")
    search_fields = ("bus_route__bus_number", "bus_route__driver_name", "notes")
    raw_id_fields = ("bus_route", "academic_year", "approved_by", "payment_voucher", "school", "branch")


@admin.register(StudentBookDistribution)
class StudentBookDistributionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "book_title", "fee_amount", "delivery_status", "delivered_at", "delivered_by", "school")
    list_filter = ("school", "delivery_status", "academic_year")
    search_fields = ("student__first_name", "student__last_name", "book_title")
    raw_id_fields = ("student", "academic_year", "delivered_by", "invoice", "school", "branch")


@admin.register(StudentBusSubscription)
class StudentBusSubscriptionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "bus_route", "academic_year", "subscription_type", "status", "school")
    list_filter = ("school", "status", "subscription_type", "academic_year")
    search_fields = ("student__user__first_name", "student__user__last_name", "bus_route__route_name")
    raw_id_fields = ("student", "bus_route", "academic_year", "school", "branch")


@admin.register(LibraryBook)
class LibraryBookAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("isbn", "title", "author", "category", "total_copies", "available_copies", "shelf_location", "school")
    list_filter = ("school", "category")
    search_fields = ("isbn", "title", "author", "publisher")


@admin.register(BookLoan)
class BookLoanAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("book", "student", "teacher", "borrow_date", "due_date", "return_date", "status", "fine_amount", "school")
    list_filter = ("school", "status", "borrow_date")
    search_fields = ("book__title", "student__user__first_name", "teacher__user__first_name")
    raw_id_fields = ("book", "student", "teacher", "school", "branch")


@admin.register(StudentHealthProfile)
class StudentHealthProfileAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "blood_type", "emergency_contact_name", "emergency_contact_phone", "school")
    list_filter = ("school", "blood_type")
    search_fields = ("student__user__first_name", "student__user__last_name", "emergency_contact_name")
    raw_id_fields = ("student", "school", "branch")


@admin.register(ClinicVisit)
class ClinicVisitAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "visit_date", "symptoms", "temperature", "sent_home", "parent_notified", "attended_by", "school")
    list_filter = ("school", "sent_home", "parent_notified", "visit_date")
    search_fields = ("student__user__first_name", "student__user__last_name", "diagnosis", "symptoms")
    raw_id_fields = ("student", "school", "branch")


from unfold.admin import TabularInline


class BookRequisitionItemInline(TabularInline):
    model = BookRequisitionItem
    extra = 1


@admin.register(BookRequisitionOrder)
class BookRequisitionOrderAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("order_number", "requested_by", "academic_year", "grade_level", "section", "status", "approved_by", "fulfilled_by", "created_at", "school")
    list_filter = ("school", "status", "academic_year")
    search_fields = ("order_number", "requested_by__phone", "requested_by__first_name", "requested_by__last_name", "notes")
    raw_id_fields = ("requested_by", "approved_by", "fulfilled_by", "academic_year", "grade_level", "section", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at", "approved_at", "fulfilled_at")
    inlines = (BookRequisitionItemInline,)


@admin.register(BookRequisitionItem)
class BookRequisitionItemAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("requisition", "book_title", "quantity_requested", "quantity_approved", "quantity_dispatched", "school")
    list_filter = ("school",)
    search_fields = ("book_title", "requisition__order_number")
    raw_id_fields = ("requisition", "school", "branch")
