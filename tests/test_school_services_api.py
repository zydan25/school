"""Contract tests for optional, school-scoped support-service APIs."""
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from apps.school_services.api import serializers as service_serializers


class SchoolServicesApiRouteTests(SimpleTestCase):
    def test_optional_service_endpoints_are_mounted_once_and_clinic_is_absent(self):
        routes = {
            "/api/v1/school-services/features/": "school-service-features",
            "/api/v1/school-services/library/policy/": "school-library-policy",
            "/api/v1/school-services/bus-routes/": "school-bus-route-list",
            "/api/v1/school-services/bus-subscriptions/": "school-bus-subscription-list",
            "/api/v1/school-services/bus-charges/": "school-bus-charge-list",
            "/api/v1/school-services/library/books/": "school-library-book-list",
            "/api/v1/school-services/library/loans/": "school-library-loan-list",
            "/api/v1/school-services/bus-settlements/": "school-bus-settlement-list",
            "/api/v1/school-services/book-distributions/": "school-book-distribution-list",
            "/api/v1/school-services/book-requisitions/": "school-book-requisition-list",
        }
        for route, expected_name in routes.items():
            with self.subTest(route=route):
                self.assertEqual(resolve(route).url_name, expected_name)

        for route in (
            "/api/v1/school-services/clinic/health-profiles/",
            "/api/v1/school-services/clinic/visits/",
        ):
            with self.subTest(route=route):
                with self.assertRaises(Resolver404):
                    resolve(route)

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
    def test_optional_school_service_serializers_build_their_fields(self):
        serializer_types = (
            service_serializers.BusRouteSerializer,
            service_serializers.StudentBusSubscriptionSerializer,
            service_serializers.BusSubscriptionChargeSerializer,
            service_serializers.LibraryBookSerializer,
            service_serializers.BookLoanSerializer,
            service_serializers.BusFinancialSettlementSerializer,
            service_serializers.StudentBookDistributionSerializer,
            service_serializers.BookRequisitionItemSerializer,
            service_serializers.BookRequisitionOrderSerializer,
        )
        errors = {}
        for serializer_type in serializer_types:
            try:
                tuple(serializer_type().fields.keys())
            except Exception as exc:
                errors[serializer_type.__name__] = f"{type(exc).__name__}: {exc}"
        self.assertEqual(errors, {})
