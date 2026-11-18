from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core.utils import format_cop, quantize_currency

User = get_user_model()

class CoreUtilitiesTestCase(TestCase):
    def test_format_cop_standard(self):
        self.assertEqual(format_cop(Decimal('1500000')), "$ 1.500.000 COP")
        self.assertEqual(format_cop(0), "$ 0 COP")
        self.assertEqual(format_cop(None), "$ 0 COP")

    def test_format_cop_cents(self):
        self.assertEqual(format_cop(Decimal('1500000.50'), show_cents=True), "$ 1.500.000,50 COP")

    def test_quantize_currency(self):
        # Strict 2 decimals with ROUND_HALF_UP
        val = quantize_currency('1500000.456')
        self.assertEqual(val, Decimal('1500000.46'))
        self.assertIsInstance(val, Decimal)


class AuthenticationAndNavigationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "StrongPassword2026!"
        self.user = User.objects.create_user(
            username="testuser",
            email="test@loanmanager.local",
            password=self.password,
            first_name="Juan",
            last_name="Perez",
            role=User.Role.ADMIN
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('users:login')))

    def test_login_page_renders_cleanly(self):
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LoanManager")
        self.assertContains(response, "Correo Electrónico")

    def test_authenticated_dashboard_access(self):
        logged_in = self.client.login(username="test@loanmanager.local", password=self.password)
        self.assertTrue(logged_in)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard Financiero")
        self.assertContains(response, "Caja Disponible")
        self.assertContains(response, "Capital Prestado")

    def test_all_sidebar_routes_resolve_with_200(self):
        """Verifies rule 8: No generes enlaces rotos."""
        self.client.login(username="test@loanmanager.local", password=self.password)
        
        routes = [
            'core:dashboard',
            'customers:list',
            'loans:list',
            'loans:create',
            'loans:installments',
            'payments:list',
            'payments:create',
            'cashflow:index',
            'portfolio:index',
            'calendar_app:index',
            'notifications:list',
            'reports:list',
            'audit:list',
            'users:profile',
            'users:change_password',
        ]

        for route_name in routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200, f"Route {route_name} failed with status {response.status_code}")

