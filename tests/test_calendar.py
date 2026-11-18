import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.calendar_app.services.calendar_builder import CalendarBuilder

User = get_user_model()

class CalendarModuleTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            email='admin_cal@test.local',
            username='admin_cal',
            password='Password123!',
            first_name='Admin',
            last_name='Calendar'
        )
        self.client.login(email='admin_cal@test.local', password='Password123!')

        self.customer = Customer.objects.create(
            first_name='Mariana',
            last_name='Gómez',
            document_type=Customer.DocumentType.CC,
            document_number='52987654',
            phone='3109876543',
            whatsapp='3109876543',
            city='Medellín'
        )

        today = timezone.localdate()
        self.today = today

        self.loan = Loan.objects.create(
            customer=self.customer,
            loan_code='LN-CAL-001',
            principal=Decimal('600000.00'),
            interest_rate=Decimal('5.00'),
            interest_type=Loan.InterestType.FLAT,
            payment_frequency=Loan.PaymentFrequency.MONTHLY,
            total_installments=2,
            disbursement_date=today - datetime.timedelta(days=40),
            first_payment_date=today - datetime.timedelta(days=10),
            total_interest=Decimal('30000.00'),
            total_amount=Decimal('630000.00'),
            paid_principal=Decimal('0.00'),
            paid_interest=Decimal('0.00'),
            balance=Decimal('630000.00'),
            status=Loan.Status.ACTIVE,
            created_by=self.user
        )

        # Overdue installment (10 days ago)
        self.inst_overdue = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=1,
            due_date=today - datetime.timedelta(days=10),
            principal_amount=Decimal('300000.00'),
            interest_amount=Decimal('15000.00'),
            total_amount=Decimal('315000.00'),
            balance=Decimal('315000.00'),
            status=Installment.Status.OVERDUE
        )

        # Upcoming installment (today + 20 days)
        self.inst_upcoming = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=2,
            due_date=today + datetime.timedelta(days=20),
            principal_amount=Decimal('300000.00'),
            interest_amount=Decimal('15000.00'),
            total_amount=Decimal('315000.00'),
            balance=Decimal('315000.00'),
            status=Installment.Status.PENDING
        )

    def test_calendar_builder_month_data(self):
        """Calendar builder must generate valid month matrix and aggregates."""
        month_data = CalendarBuilder.get_month_data(
            year=self.today.year,
            month=self.today.month,
            today=self.today
        )

        self.assertIn('weeks', month_data)
        self.assertIn('month_name', month_data)
        self.assertGreaterEqual(len(month_data['weeks']), 4)
        
        # Check that each week contains exactly 7 days
        for week in month_data['weeks']:
            self.assertEqual(len(week), 7)

        # Total due for this month should include installments in this month
        self.assertIsInstance(month_data['month_total_due'], Decimal)
        self.assertIsInstance(month_data['month_total_pending'], Decimal)

    def test_calendar_builder_day_agenda(self):
        """Day agenda must detail scheduled cuotas and produce WhatsApp reminder URLs."""
        agenda = CalendarBuilder.get_day_agenda(target_date=self.inst_overdue.due_date)

        self.assertEqual(agenda['total_count'], 1)
        self.assertEqual(agenda['overdue_count'], 1)
        self.assertEqual(agenda['total_due'], Decimal('315000.00'))
        self.assertEqual(agenda['total_balance'], Decimal('315000.00'))

        item = agenda['installments'][0]
        self.assertEqual(item['customer'], self.customer)
        self.assertTrue(item['is_overdue'])
        self.assertIsNotNone(item['whatsapp_url'])
        self.assertIn('573109876543', item['whatsapp_url'])
        self.assertIn('LN-CAL-001', item['whatsapp_url'])

    def test_views_calendar_and_htmx_agenda(self):
        """HTTP endpoints for calendar and dynamic day agenda."""
        # 1. Main calendar view
        response = self.client.get(reverse('calendar_app:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calendario de Cobros')
        self.assertContains(response, 'Compromisos del Mes')

        # 2. Main calendar with specific month
        response = self.client.get(
            reverse('calendar_app:index') + f'?year={self.today.year}&month={self.today.month}&status=OVERDUE'
        )
        self.assertEqual(response.status_code, 200)

        # 3. Dynamic HTMX Day Agenda endpoint
        date_str = self.inst_overdue.due_date.strftime('%Y-%m-%d')
        response = self.client.get(reverse('calendar_app:day_agenda', kwargs={'date_str': date_str}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.full_name)
        self.assertContains(response, 'LN-CAL-001')
        self.assertContains(response, 'En Mora')

