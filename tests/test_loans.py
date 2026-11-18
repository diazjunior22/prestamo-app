import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.loans.services.loan_calculator import LoanCalculator
from apps.loans.services.loan_creator import LoanCreator
from apps.cashflow.models import CashMovement

User = get_user_model()

class FinancialEngineTestCase(TestCase):
    def test_flat_rate_calculation_and_cent_conservation(self):
        principal = Decimal('1000000.00')
        interest_rate = Decimal('5.00') # 5% per month
        installments = 6
        first_date = datetime.date(2026, 12, 1)

        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=interest_rate,
            interest_type='FLAT',
            frequency='MONTHLY',
            total_installments=installments,
            first_payment_date=first_date
        )

        # 5% of 1,000,000 = 50,000 per installment * 6 = 300,000 total interest
        self.assertEqual(schedule['total_interest'], Decimal('300000.00'))
        self.assertEqual(schedule['total_amount'], Decimal('1300000.00'))
        self.assertEqual(len(schedule['installments']), 6)

        # Cent conservation rule: sum of principals must equal initial principal exactly
        sum_p = sum(item['principal'] for item in schedule['installments'])
        self.assertEqual(sum_p, principal)

        # Sum of interests must equal total interest exactly
        sum_i = sum(item['interest'] for item in schedule['installments'])
        self.assertEqual(sum_i, Decimal('300000.00'))

    def test_french_amortization_calculation_and_cent_conservation(self):
        principal = Decimal('5000000.00')
        interest_rate = Decimal('2.50') # 2.5% per month
        installments = 12
        first_date = datetime.date(2026, 12, 15)

        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=interest_rate,
            interest_type='AMORTIZED_REDUCING',
            frequency='MONTHLY',
            total_installments=installments,
            first_payment_date=first_date
        )

        self.assertEqual(len(schedule['installments']), 12)
        sum_p = sum(item['principal'] for item in schedule['installments'])
        self.assertEqual(sum_p, principal)
        self.assertEqual(schedule['installments'][-1]['balance_after'], Decimal('0.00'))

    def test_zero_interest_calculation(self):
        principal = Decimal('300000.00')
        installments = 3
        first_date = datetime.date(2026, 12, 1)

        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('0.00'),
            interest_type='NO_INTEREST',
            frequency='MONTHLY',
            total_installments=installments,
            first_payment_date=first_date
        )

        self.assertEqual(schedule['total_interest'], Decimal('0.00'))
        self.assertEqual(schedule['total_amount'], principal)
        for item in schedule['installments']:
            self.assertEqual(item['principal'], Decimal('100000.00'))
            self.assertEqual(item['interest'], Decimal('0.00'))


class LoanCreationAndViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "SecPass2026!"
        self.user = User.objects.create_user(
            username="loan_officer",
            email="officer@loanmanager.local",
            password=self.password,
            first_name="Diana",
            last_name="Prestamista",
            role=User.Role.ADMIN
        )
        self.client.login(username="officer@loanmanager.local", password=self.password)

        self.customer = Customer.objects.create(
            first_name="Beatriz",
            last_name="Pinzón",
            document_type=Customer.DocumentType.CC,
            document_number="52987654",
            phone="3115556677",
            status=Customer.Status.ACTIVE,
            created_by=self.user
        )

    def test_atomic_loan_origination_service(self):
        disb_date = datetime.date(2026, 11, 18)
        first_date = datetime.date(2026, 12, 18)

        loan = LoanCreator.create_loan(
            customer=self.customer,
            principal=Decimal('2000000.00'),
            interest_rate=Decimal('5.00'),
            interest_type='FLAT',
            payment_frequency='MONTHLY',
            total_installments=5,
            disbursement_date=disb_date,
            first_payment_date=first_date,
            notes="Préstamo microempresa",
            user=self.user
        )

        self.assertIsNotNone(loan.pk)
        self.assertTrue(loan.loan_code.startswith("LN-"))
        self.assertEqual(loan.installments.count(), 5)
        self.assertEqual(loan.balance, loan.total_amount)
        self.assertEqual(loan.status, Loan.Status.ACTIVE)

        # Check atomic CashMovement
        outflow = CashMovement.objects.filter(loan_reference=loan.loan_code).first()
        self.assertIsNotNone(outflow)
        self.assertEqual(outflow.amount, Decimal('2000000.00'))
        self.assertEqual(outflow.movement_type, CashMovement.MovementType.LOAN_DISBURSEMENT)

    def test_loan_create_view_form_submission(self):
        data = {
            'customer': str(self.customer.pk),
            'principal': '1500000',
            'interest_type': 'FLAT',
            'interest_rate': '4.0',
            'payment_frequency': 'MONTHLY',
            'total_installments': '6',
            'disbursement_date': '2026-11-20',
            'first_payment_date': '2026-12-20',
            'notes': 'Contrato firmado',
        }
        response = self.client.post(reverse('loans:create'), data=data)
        self.assertEqual(response.status_code, 302)

        loan = Loan.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(loan)
        self.assertEqual(loan.principal, Decimal('1500000.00'))
        self.assertEqual(loan.installments.count(), 6)

    def test_loan_simulate_htmx_endpoint(self):
        url = reverse('loans:simulate') + '?principal=1000000&interest_rate=5.0&interest_type=FLAT&payment_frequency=MONTHLY&total_installments=4&first_payment_date=2026-12-01'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Capital")
        self.assertContains(response, "Interés Total")
        self.assertContains(response, "1.000.000")

    def test_loan_detail_view(self):
        loan = LoanCreator.create_loan(
            customer=self.customer,
            principal=Decimal('1000000.00'),
            interest_rate=Decimal('5.00'),
            interest_type='FLAT',
            payment_frequency='MONTHLY',
            total_installments=4,
            disbursement_date=datetime.date(2026, 11, 18),
            first_payment_date=datetime.date(2026, 12, 18),
            user=self.user
        )
        response = self.client.get(reverse('loans:detail', kwargs={'pk': loan.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, loan.loan_code)
        self.assertContains(response, "Beatriz Pinzón")
        self.assertContains(response, "Plan de Amortización")

    def test_installment_list_view(self):
        LoanCreator.create_loan(
            customer=self.customer,
            principal=Decimal('800000.00'),
            interest_rate=Decimal('3.00'),
            interest_type='FLAT',
            payment_frequency='MONTHLY',
            total_installments=3,
            disbursement_date=datetime.date(2026, 11, 18),
            first_payment_date=datetime.date(2026, 12, 18),
            user=self.user
        )
        response = self.client.get(reverse('loans:installments'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cronograma Global de Cuotas")
        self.assertContains(response, "Beatriz Pinzón")

