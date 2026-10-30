from django.test import SimpleTestCase


class CoreConfigurationTests(SimpleTestCase):
    def test_platform_root_is_public_health_landing(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "School")
