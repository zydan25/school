"""Contract smoke tests for the canonical and v1 mobile API surface."""
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve
from rest_framework import serializers as drf_serializers

from apps.api import v1 as mobile_v1_serializers


class MobileSerializerContractTests(SimpleTestCase):
    def test_all_declared_mobile_serializers_can_build_fields(self):
        """Catch invalid ModelSerializer Meta fields as soon as a contract is added."""
        serializer_types = [
            value
            for value in vars(mobile_v1_serializers).values()
            if isinstance(value, type)
            and issubclass(value, drf_serializers.BaseSerializer)
            and value is not drf_serializers.BaseSerializer
            and value.__module__ == mobile_v1_serializers.__name__
        ]
        self.assertGreaterEqual(len(serializer_types), 50)

        errors = {}
        for serializer_type in serializer_types:
            try:
                tuple(serializer_type().fields.keys())
            except Exception as exc:  # report every bad contract in one test run
                errors[serializer_type.__name__] = f"{type(exc).__name__}: {exc}"

        self.assertEqual(errors, {}, msg=f"Invalid mobile serializers: {errors}")


class CanonicalApiRouteTests(SimpleTestCase):
    def test_existing_api_contracts_are_reused_not_shadowed_under_app_prefix(self):
        """The new mobile namespace must not duplicate endpoints already shipped."""
        canonical_routes = {
            "/api/v1/me/": "current-user",
            "/api/v1/students/": "student-list",
            "/api/v1/notifications/": "user-notifications",
            "/api/v1/staff/members/": "staff-list",
            "/api/v1/fees/invoices/": "invoice-list-create",
            "/api/v1/payroll/runs/": "payroll-run-list",
            "/api/v1/attendance/registers/": "attendance-register-list",
            "/api/v1/timetable/ai-generate/": "ai-generate",
        }
        for path, expected_name in canonical_routes.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, expected_name)

        # These routes were intentionally not re-declared in the mobile namespace.
        for duplicate_path in (
            "/api/v1/app/me/",
            "/api/v1/app/students/",
            "/api/v1/app/staff-members/",
            "/api/v1/app/notifications/feed/",
        ):
            with self.subTest(path=duplicate_path):
                with self.assertRaises(Resolver404):
                    resolve(duplicate_path)

    def test_new_mobile_only_resources_have_one_canonical_route(self):
        routes = {
            "/api/v1/app/account/profiles/": "app-my-profiles",
            "/api/v1/app/account/invitations/": "app-invitations",
            "/api/v1/app/account/invitations/accept/": "app-invitation-accept",
            "/api/v1/app/account/invitations/00000000-0000-0000-0000-000000000001/revoke/": "app-invitation-revoke",
            "/api/v1/app/my/children/": "app-my-children",
            "/api/v1/app/my/timetable/": "app-my-timetable",
            "/api/v1/app/homework/": "app-homework-list",
            "/api/v1/app/homework-submissions/": "app-homework-submission-list",
            "/api/v1/app/online-exams/": "app-online-exam-list",
            "/api/v1/app/conversations/": "app-conversation-list",
            "/api/v1/app/devices/": "app-push-device-list",
        }
        for path, expected_name in routes.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, expected_name)
