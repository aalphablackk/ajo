
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .forms import RegistrationForm

User = get_user_model()


class RegistrationTests(TestCase):

    def setUp(self):
        self.register_url = reverse("accounts:register")

        self.user_data = {
            "email": "james@example.com",
            "full_name": "James Akintoye",
            "phone_number": "08012345678",
            "password1": "StrongPassword!2026",
            "password2": "StrongPassword!2026",
        }

    def test_registration_page_loads(self):
        response = self.client.get(self.register_url)

        self.assertEqual(response.status_code, 200)

    def test_user_can_register(self):
        response = self.client.post(
            self.register_url,
            self.user_data
        )

        self.assertRedirects(
            response,
            reverse("accounts:login")
        )

        self.assertTrue(
            User.objects.filter(email="james@example.com").exists()
        )

    def test_password_is_hashed(self):
        self.client.post(self.register_url, self.user_data)

        user = User.objects.get(email="james@example.com")

        self.assertNotEqual(
            user.password,
            self.user_data["password1"]
        )

        self.assertTrue(
            user.check_password(self.user_data["password1"])
        )

    def test_duplicate_email_is_rejected(self):
        self.client.post(self.register_url, self.user_data)

        response = self.client.post(
            self.register_url,
            self.user_data
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(
            email="james@example.com"
        ).count(), 1)

    def test_mismatched_passwords_are_rejected(self):
        data = self.user_data.copy()
        data["password2"] = "DifferentPassword!2026"

        response = self.client.post(self.register_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(email="james@example.com").exists()
        )


class LoginTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="james@example.com",
            full_name="James Akintoye",
            password="StrongPassword!2026"
        )

        self.login_url = reverse("accounts:login")
        self.dashboard_url = reverse("accounts:dashboard")
        self.logout_url = reverse("accounts:logout")

    def test_user_can_login(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "james@example.com",
                "password": "StrongPassword!2026",
            }
        )

        self.assertRedirects(response, self.dashboard_url)

    def test_invalid_login_is_rejected(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "james@example.com",
                "password": "WrongPassword!2026",
            }
        )

        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get(self.dashboard_url)

        self.assertRedirects(
            response,
            f"{self.login_url}?next={self.dashboard_url}"
        )

    def test_authenticated_user_can_access_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)

    def test_user_can_logout(self):
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url)

        self.assertRedirects(response, self.login_url)

        response = self.client.get(self.dashboard_url)

        self.assertRedirects(
            response,
            f"{self.login_url}?next={self.dashboard_url}"
        )
