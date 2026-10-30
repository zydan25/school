from django.test import SimpleTestCase


class PublicApiTests(SimpleTestCase):
    def test_versioned_health_endpoint(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_root_returns_service_identity(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name_ar"], "سكول")
