import re

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import DeviceSession, User


class IdentitySessionSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def create_user(self, phone="+967770007701", **extra):
        return User.objects.create_user(
            phone=phone,
            password="Strong-Password-7701!",
            first_name="مستخدم",
            last_name="اختبار",
            **extra,
        )

    def test_login_issues_independent_device_sessions_and_revokes_only_selected_device(self):
        user = self.create_user()
        first = self.client.post(
            "/api/v1/auth/login/",
            {"phone": user.phone, "password": "Strong-Password-7701!", "device_id": "android-1"},
            format="json",
        )
        second = self.client.post(
            "/api/v1/auth/login/",
            {"phone": user.phone, "password": "Strong-Password-7701!", "device_id": "android-2"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertNotEqual(first.data["access_token"], second.data["access_token"])
        self.assertEqual(DeviceSession.objects.filter(user=user, revoked_at__isnull=True).count(), 2)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {first.data['access_token']}")
        listing = self.client.get("/api/v1/auth/sessions/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data["results"]), 2)

        revoked = self.client.post(
            f"/api/v1/auth/sessions/{second.data['session_id']}/revoke/",
            {},
            format="json",
        )
        self.assertEqual(revoked.status_code, status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {second.data['access_token']}")
        rejected = self.client.get("/api/v1/me/")
        self.assertEqual(rejected.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {first.data['access_token']}")
        accepted = self.client.get("/api/v1/me/")
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)

    def test_session_refresh_rotates_secret_and_old_secret_stops_working(self):
        user = self.create_user()
        login = self.client.post(
            "/api/v1/auth/login/",
            {"phone": user.phone, "password": "Strong-Password-7701!", "device_id": "tablet-1"},
            format="json",
        )
        old_token = login.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_token}")
        refreshed = self.client.post("/api/v1/auth/sessions/refresh/", {}, format="json")
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertNotEqual(old_token, refreshed.data["access_token"])

        old_client = APIClient()
        old_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_token}")
        self.assertEqual(old_client.get("/api/v1/me/").status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access_token']}")
        self.assertEqual(self.client.get("/api/v1/me/").status_code, status.HTTP_200_OK)

    def test_failed_login_attempts_temporarily_lock_account(self):
        user = self.create_user(phone="+967770007702")
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/login/",
                {"phone": user.phone, "password": "incorrect-password"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        user.refresh_from_db()
        self.assertIsNotNone(user.locked_until)
        self.assertGreater(user.locked_until, timezone.now())

        blocked = self.client.post(
            "/api/v1/auth/login/",
            {"phone": user.phone, "password": "Strong-Password-7701!"},
            format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_423_LOCKED)

    def test_phone_registration_requires_otp_and_activates_only_after_verification(self):
        from unittest.mock import patch

        sent = []

        def fake_sender(*, phone, message, purpose):
            sent.append((phone, message, purpose))
            return True

        with patch("apps.accounts.session_services.send_phone_message", side_effect=fake_sender):
            registered = self.client.post(
                "/api/v1/auth/register/",
                {
                    "phone": "+967770007703",
                    "first_name": "أمل",
                    "last_name": "محمد",
                    "password": "Strong-Register-7703!",
                    "password_confirm": "Strong-Register-7703!",
                },
                format="json",
            )
            self.assertEqual(registered.status_code, status.HTTP_202_ACCEPTED)

            user = User.objects.get(phone="+967770007703")
            self.assertFalse(user.is_active)
            self.assertEqual(user.status, User.Status.PENDING)
            self.assertIsNone(user.phone_verified_at)

            code_match = re.search(r"(\d{6})", sent[-1][1])
            self.assertIsNotNone(code_match)
            verified = self.client.post(
                "/api/v1/auth/phone/verify/",
                {"phone": user.phone, "code": code_match.group(1)},
                format="json",
            )

        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.status, User.Status.ACTIVE)
        self.assertIsNotNone(user.phone_verified_at)

    def test_password_reset_revokes_all_existing_device_sessions(self):
        from unittest.mock import patch

        user = self.create_user(phone="+967770007704")
        user.phone_verified_at = timezone.now()
        user.save(update_fields=["phone_verified_at", "updated_at"])
        login = self.client.post(
            "/api/v1/auth/login/",
            {"phone": user.phone, "password": "Strong-Password-7701!", "device_id": "old-phone"},
            format="json",
        )
        old_token = login.data["access_token"]
        sent = []

        def fake_sender(*, phone, message, purpose):
            sent.append(message)
            return True

        with patch("apps.accounts.session_services.send_phone_message", side_effect=fake_sender):
            requested = self.client.post(
                "/api/v1/auth/password/reset/request/",
                {"phone": user.phone},
                format="json",
            )
            self.assertEqual(requested.status_code, status.HTTP_202_ACCEPTED)
            code = re.search(r"(\d{6})", sent[-1]).group(1)
            reset = self.client.post(
                "/api/v1/auth/password/reset/confirm/",
                {
                    "phone": user.phone,
                    "code": code,
                    "new_password": "New-Strong-Password-7704!",
                    "password_confirm": "New-Strong-Password-7704!",
                },
                format="json",
            )

        self.assertEqual(reset.status_code, status.HTTP_200_OK)
        self.assertEqual(
            DeviceSession.objects.filter(user=user, revoked_at__isnull=True).count(),
            0,
        )
        old_client = APIClient()
        old_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_token}")
        self.assertEqual(old_client.get("/api/v1/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(User.objects.get(pk=user.pk).check_password("New-Strong-Password-7704!"))

    def test_legacy_token_and_bearer_authentication_remain_supported(self):
        from rest_framework.authtoken.models import Token

        user = self.create_user(phone="+967770007705")
        token, _ = Token.objects.get_or_create(user=user)
        for prefix in ("Token", "Bearer"):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"{prefix} {token.key}")
            response = client.get("/api/v1/me/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
