import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.cashflow.models import CashMovement
from apps.payments.models import Payment
from apps.payments.services.payment_allocator import allocate_payment
from apps.core.services.dashboard_service import DashboardService

User = get_user_model()

class DashboardTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            email='admin_dash@test.local',
            username='admin_dash',
            password='Password123!',
            first_name='Admin',
            last_name='Dash'
        )
        self.client.login(email='admin_dash@test.local', password='Password123!')

        today = timezone.localdate()
        self.today = today

        # Initial capital in cash drawer: $5,000,000 COP
        CashMovement.objects.create(
            movement_type=CashMovement.MovementType.CAPITAL_INJECTION,
            amount=Decimal('5000000.00'),
            movement_date=today - datetime.timedelta(days=30),
            description='Aporte de capital inicial'
        )

        self.customer = Customer.objects.create(
            first_name='Laura',
            last_name='Restrepo',
            document_type=Customer.DocumentType.CC,
            document_number='43890123',
            phone='3115559988',
            whatsapp='3115559988',
            city='Cali'
        )

        # Loan of $2,000,000 at 10% flat -> Total $2,200,000 (Principal: $2,000,000, Interest: $200,000)
        # 2 installments of $1,100,000 ($1,000,000 principal + $100,000 interest)
        # Installment 1 due TODAY
        # Installment 2 due in 30 days
        self.loan = Loan.objects.create(
            customer=self.customer,
            loan_code='LN-DASH-01',
            principal=Decimal('2000000.00'),
            interest_rate=Decimal('10.00'),
            interest_type=Loan.InterestType.FLAT,
            payment_frequency=Loan.PaymentFrequency.MONTHLY,
            total_installments=2,
            disbursement_date=today - datetime.timedelta(days=15),
            first_payment_date=today,
            total_interest=Decimal('200000.00'),
            total_amount=Decimal('2200000.00'),
            paid_principal=Decimal('0.00'),
            paid_interest=Decimal('0.00'),
            balance=Decimal('2200000.00'),
            status=Loan.Status.ACTIVE,
            created_by=self.user
        )

        CashMovement.objects.create(
            movement_type=CashMovement.MovementType.LOAN_DISBURSEMENT,
            amount=Decimal('2000000.00'),
            movement_date=today - datetime.timedelta(days=15),
            description=f"Desembolso {self.loan.loan_code}",
            loan_reference=self.loan.loan_code
        )

        self.inst1 = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=1,
            due_date=today,
            principal_amount=Decimal('1000000.00'),
            interest_amount=Decimal('100000.00'),
            total_amount=Decimal('1100000.00'),
            balance=Decimal('1100000.00'),
            status=Installment.Status.PENDING
        )

        self.inst2 = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=2,
            due_date=today + datetime.timedelta(days=30),
            principal_amount=Decimal('1000000.00'),
            interest_amount=Decimal('100000.00'),
            total_amount=Decimal('1100000.00'),
            balance=Decimal('1100000.00'),
            status=Installment.Status.PENDING
        )

    def test_dashboard_kpis_before_and_after_payment(self):
        """KPIs must calculate accurately from actual database records."""
        # Initial cash: $5,000,000 - $2,000,000 = $3,000,000
        kpis = DashboardService.get_kpis(today=self.today)
        self.assertEqual(kpis['available_capital'], Decimal('3000000.00'))
        self.assertEqual(kpis['lent_capital'], Decimal('2000000.00'))
        self.assertEqual(kpis['pending_principal'], Decimal('2000000.00'))
        self.assertEqual(kpis['pending_interest'], Decimal('200000.00'))
        self.assertEqual(kpis['collected_interest'], Decimal('0.00'))
        self.assertEqual(kpis['today_due_amount'], Decimal('1100000.00'))
        self.assertEqual(kpis['active_loans_count'], 1)
        self.assertEqual(kpis['overdue_installments_count'], 0)

        # Now pay Installment 1 ($1,100,000: $100,000 interest + $1,000,000 principal)
        payment = allocate_payment(
            loan=self.loan,
            amount=Decimal('1100000.00'),
            payment_date=self.today,
            user=self.user
        )

        kpis_after = DashboardService.get_kpis(today=self.today)
        # Cash increases by $1,100,000 -> $4,100,000
        self.assertEqual(kpis_after['available_capital'], Decimal('4100000.00'))
        self.assertEqual(kpis_after['pending_principal'], Decimal('1000000.00'))
        self.assertEqual(kpis_after['collected_interest'], Decimal('100000.00'))
        self.assertEqual(kpis_after['pending_interest'], Decimal('100000.00'))
        self.assertEqual(kpis_after['today_due_amount'], Decimal('0.00'))

    def test_chart_flow_and_portfolio_health(self):
        """Chart flow and portfolio health services return valid structured data."""
        flow = DashboardService.get_chart_flow_data(year=self.today.year)
        self.assertEqual(len(flow['labels']), 12)
        self.assertEqual(len(flow['disbursements']), 12)
        self.assertEqual(len(flow['collections']), 12)
        self.assertGreaterEqual(flow['disbursements'][self.today.month - 1], 2000000.0)

        health = DashboardService.get_portfolio_health(today=self.today)
        self.assertEqual(len(health['donut_data']), 3)
        self.assertEqual(health['on_time_pct'], 100.0)
        self.assertEqual(health['mild_delay_pct'], 0.0)
        self.assertEqual(health['critical_delay_pct'], 0.0)

    def test_upcoming_installments_and_recent_activities(self):
        """Upcoming list and activity feed correctly populate."""
        upcoming = DashboardService.get_upcoming_installments(today=self.today, limit=5)
        self.assertEqual(len(upcoming), 1)  # Only inst1 due today; inst2 is 30 days away
        self.assertEqual(upcoming[0]['customer_name'], self.customer.full_name)
        self.assertEqual(upcoming[0]['amount'], Decimal('1100000.00'))
        self.assertTrue(upcoming[0]['is_today'])

        activities = DashboardService.get_recent_activities(limit=5)
        self.assertGreaterEqual(len(activities), 1)
        self.assertIn('LN-DASH-01', activities[0]['description'])

    def test_dashboard_view_http(self):
        """Dashboard view returns HTTP 200 with all context elements."""
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard Financiero')
        self.assertContains(response, 'Caja Disponible')
        self.assertContains(response, 'LN-DASH-01')
        self.assertContains(response, 'monthlyFlowChart')
        self.assertContains(response, 'portfolioHealthChart')

