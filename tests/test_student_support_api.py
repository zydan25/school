"""Route and serializer contract tests for missing student support APIs."""
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework import serializers as drf_serializers

from apps.students.api import support_serializers


class StudentSupportApiRouteTests(SimpleTestCase):
    def test_missing_student_support_endpoints_are_added_to_the_existing_students_api(self):
        routes = {
            "/api/v1/students/incidents/": "student-incident-list-create",
            "/api/v1/students/incidents/00000000-0000-0000-0000-000000000001/": "student-incident-detail",
            "/api/v1/students/incidents/00000000-0000-0000-0000-000000000001/notify-parents/": "student-incident-notify-parents",
            "/api/v1/students/incidents/00000000-0000-0000-0000-000000000001/seen/": "student-incident-seen",
            "/api/v1/students/incidents/00000000-0000-0000-0000-000000000001/resolve/": "student-incident-resolve",
            "/api/v1/students/summons/": "student-summon-list-create",
            "/api/v1/students/summons/00000000-0000-0000-0000-000000000001/": "student-summon-detail",
            "/api/v1/students/summons/00000000-0000-0000-0000-000000000001/attend/": "student-summon-attend",
            "/api/v1/students/complaints/": "student-complaint-list-create",
            "/api/v1/students/complaints/00000000-0000-0000-0000-000000000001/": "student-complaint-detail",
            "/api/v1/students/complaints/00000000-0000-0000-0000-000000000001/review/": "student-complaint-review",
        }
        for route, expected_name in routes.items():
            with self.subTest(route=route):
                self.assertEqual(resolve(route).url_name, expected_name)

    def test_existing_student_routes_keep_their_original_names(self):
        routes = {
            "/api/v1/students/": "student-list",
            "/api/v1/students/00000000-0000-0000-0000-000000000001/": "student-detail",
            "/api/v1/students/00000000-0000-0000-0000-000000000001/promote/": "student-promote",
            "/api/v1/students/00000000-0000-0000-0000-000000000001/retain/": "student-retain",
            "/api/v1/students/00000000-0000-0000-0000-000000000001/graduate/": "student-graduate",
            "/api/v1/students/00000000-0000-0000-0000-000000000001/withdraw/": "student-withdraw",
        }
        for route, expected_name in routes.items():
            with self.subTest(route=route):
                self.assertEqual(resolve(route).url_name, expected_name)

    def test_student_support_serializers_build_fields(self):
        serializer_types = [
            value for value in vars(support_serializers).values()
            if isinstance(value, type)
            and issubclass(value, drf_serializers.BaseSerializer)
            and value.__module__ == support_serializers.__name__
            and value.__name__ != "StudentSupportTenantSerializer"
        ]
        errors = {}
        for serializer_type in serializer_types:
            try:
                tuple(serializer_type().fields.keys())
            except Exception as exc:
                errors[serializer_type.__name__] = f"{type(exc).__name__}: {exc}"
        self.assertEqual(errors, {})
