"""School support services administration with Unfold RTL support."""
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.school_services.models import (
    BusRoute,
    StudentBusSubscription,
    LibraryBook,
    BookLoan,
    StudentHealthProfile,
    ClinicVisit,
)


@admin.register(BusRoute)
class BusRouteAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("route_code", "route_name", "bus_number", "driver_name", "driver_phone", "bus_capacity", "monthly_fee", "is_active", "school")
    list_filter = ("school", "is_active")
    search_fields = ("route_code", "route_name", "bus_number", "driver_name", "driver_phone")


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
