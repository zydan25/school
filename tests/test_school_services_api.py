"""Contract tests for the dedicated school-services API module."""
from django.test import SimpleTestCase
from django.urls import resolve

from apps.school_services.api import serializers as service_serializers


class SchoolServicesApiRouteTests(SimpleTestCase):
    def test_school_services_endpoints_are_mounted_once(self):
        routes = {
            "/api/v1/school-services/bus-routes/": "school-bus-route-list",
            "/api/v1/school-services/bus-subscriptions/": "school-bus-subscription-list",
            "/api/v1/school-services/library/books/": "school-library-book-list",
            "/api/v1/school-services/library/loans/": "school-library-loan-list",
            "/api/v1/school-services/bus-settlements/": "school-bus-settlement-list",
            "/api/v1/school-services/book-distributions/": "school-book-distribution-list",
            "/api/v1/school-services/book-requisitions/": "school-book-requisition-list",
            "/api/v1/school-services/clinic/health-profiles/": "school-health-profile-list",
            "/api/v1/school-services/clinic/visits/": "school-clinic-visit-list",
        }
        for route, expected_name in routes.items():
            with self.subTest(route=route):
                self.assertEqual(resolve(route).url_name, expected_name)

    def test_existing_app_owned_api_routes_remain_canonical(self):
        existing = {
            "/api/v1/students/": "student-list",
            "/api/v1/staff/members/": "staff-list",
            "/api/v1/fees/invoices/": "invoice-list-create",
            "/api/v1/payroll/runs/": "payroll-run-list",
            "/api/v1/attendance/registers/": "attendance-register-list",
            "/api/v1/notifications/": "user-notifications",
            "/api/v1/timetable/ai-generate/": "ai-generate",
        }
        for route, expected_name in existing.items():
            with self.subTest(route=route):
                self.assertEqual(resolve(route).url_name, expected_name)


class SchoolServicesSerializerContractTests(SimpleTestCase):
    def test_all_school_services_serializers_build_their_fields(self):
        serializer_types = (
            service_serializers.BusRouteSerializer,
            service_serializers.StudentBusSubscriptionSerializer,
            service_serializers.LibraryBookSerializer,
            service_serializers.BookLoanSerializer,
            service_serializers.BusFinancialSettlementSerializer,
            service_serializers.StudentBookDistributionSerializer,
            service_serializers.BookRequisitionItemSerializer,
            service_serializers.BookRequisitionOrderSerializer,
            service_serializers.StudentHealthProfileSerializer,
            service_serializers.ClinicVisitSerializer,
        )
        errors = {}
        for serializer_type in serializer_types:
            try:
                tuple(serializer_type().fields.keys())
            except Exception as exc:
                errors[serializer_type.__name__] = f"{type(exc).__name__}: {exc}"
        self.assertEqual(errors, {})
