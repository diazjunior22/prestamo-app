import datetime
import io
from decimal import Decimal
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
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
            self.assertEqual(item['principal'], Decimal('1000000.00') if principal == Decimal('3000000.00') else Decimal('100000.00'))
            self.assertEqual(item['interest'], Decimal('0.00'))


class SevenRequiredLoanScenariosTestCase(TestCase):
    """
    Verification of the 7 required scenarios from the prompt:
    1. Préstamo diario de 30 cuotas
    2. Préstamo semanal de 12 cuotas
    3. Préstamo quincenal de 12 cuotas (estricto 15 días)
    4. Préstamo mensual de 12 cuotas (meses calendario)
    5. Préstamo sin intereses
    6. Préstamo con intereses (FLAT y AMORTIZED_REDUCING)
    7. Préstamo con ajuste de última cuota por redondeo (conservación exacta de centavos)
    """

    def test_scenario_1_daily_loan_30_installments(self):
        """1. Préstamo diario de 30 cuotas = 30 vencimientos diarios consecutivos"""
        principal = Decimal('1000000.00')
        start_date = datetime.date(2027, 1, 1)
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('10.00'),
            interest_rate_period='MONTHLY',
            interest_type='FLAT',
            frequency='DAILY',
            total_installments=30,
            first_payment_date=start_date
        )

        self.assertEqual(len(schedule['installments']), 30)
        self.assertEqual(schedule['frequency_name'], 'Diario')

        # Check due dates: each day is +1 day
        for i, inst in enumerate(schedule['installments']):
            expected_date = start_date + datetime.timedelta(days=i)
            self.assertEqual(inst['due_date'], expected_date)

        # 10% monthly over 30 days is 10% total interest = 100,000 COP
        self.assertEqual(schedule['total_interest'], Decimal('100000.00'))
        self.assertEqual(schedule['total_amount'], Decimal('1100000.00'))

        # Cent conservation: sum of principals == principal
        self.assertEqual(sum(i['principal'] for i in schedule['installments']), principal)
        self.assertEqual(sum(i['interest'] for i in schedule['installments']), Decimal('100000.00'))

    def test_scenario_2_weekly_loan_12_installments(self):
        """2. Préstamo semanal de 12 cuotas = 12 vencimientos semanales (+7 días)"""
        principal = Decimal('1200000.00')
        start_date = datetime.date(2027, 2, 1)
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('8.00'),
            interest_rate_period='MONTHLY',
            interest_type='FLAT',
            frequency='WEEKLY',
            total_installments=12,
            first_payment_date=start_date
        )

        self.assertEqual(len(schedule['installments']), 12)
        self.assertEqual(schedule['frequency_name'], 'Semanal')

        # Check due dates: each week is +7 days
        for i, inst in enumerate(schedule['installments']):
            expected_date = start_date + datetime.timedelta(days=i * 7)
            self.assertEqual(inst['due_date'], expected_date)

        # Sum of principals == principal
        self.assertEqual(sum(i['principal'] for i in schedule['installments']), principal)

    def test_scenario_3_biweekly_loan_12_installments_strictly_15_days(self):
        """3. Préstamo quincenal de 12 cuotas = 12 vencimientos cada 15 días exactos"""
        principal = Decimal('2400000.00')
        start_date = datetime.date(2027, 3, 1)
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('6.00'),
            interest_rate_period='MONTHLY',
            interest_type='FLAT',
            frequency='BIWEEKLY',
            total_installments=12,
            first_payment_date=start_date
        )

        self.assertEqual(len(schedule['installments']), 12)
        self.assertEqual(schedule['frequency_name'], 'Quincenal')

        # Check due dates: strictly +15 days per installment
        for i, inst in enumerate(schedule['installments']):
            expected_date = start_date + datetime.timedelta(days=i * 15)
            self.assertEqual(inst['due_date'], expected_date)

        # Rate check: 6% monthly rate => 3% per 15-day quincena.
        # 12 quincenas * 3% = 36% total interest on 2,400,000 = 864,000
        self.assertEqual(schedule['periodic_rate_pct'], Decimal('3.00'))
        self.assertEqual(schedule['total_interest'], Decimal('864000.00'))
        self.assertEqual(sum(i['principal'] for i in schedule['installments']), principal)

    def test_scenario_4_monthly_loan_12_installments_calendar_months(self):
        """4. Préstamo mensual de 12 cuotas = 12 vencimientos mensuales (meses calendario)"""
        principal = Decimal('3600000.00')
        start_date = datetime.date(2027, 1, 15)
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('4.00'),
            interest_rate_period='MONTHLY',
            interest_type='FLAT',
            frequency='MONTHLY',
            total_installments=12,
            first_payment_date=start_date
        )

        self.assertEqual(len(schedule['installments']), 12)
        self.assertEqual(schedule['frequency_name'], 'Mensual')

        # Check calendar months progression preserving day 15
        expected_months = [
            (2027, 1, 15), (2027, 2, 15), (2027, 3, 15), (2027, 4, 15),
            (2027, 5, 15), (2027, 6, 15), (2027, 7, 15), (2027, 8, 15),
            (2027, 9, 15), (2027, 10, 15), (2027, 11, 15), (2027, 12, 15)
        ]
        for inst, (y, m, d) in zip(schedule['installments'], expected_months):
            self.assertEqual(inst['due_date'], datetime.date(y, m, d))

        self.assertEqual(sum(i['principal'] for i in schedule['installments']), principal)

    def test_scenario_5_zero_interest(self):
        """5. Préstamo sin intereses (NO_INTEREST): distribuye solo capital, 0 interés"""
        principal = Decimal('750000.00')
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('0.00'),
            interest_type='NO_INTEREST',
            frequency='BIWEEKLY',
            total_installments=5,
            first_payment_date=datetime.date(2027, 5, 1)
        )

        self.assertEqual(schedule['total_interest'], Decimal('0.00'))
        self.assertEqual(schedule['total_amount'], principal)
        for inst in schedule['installments']:
            self.assertEqual(inst['interest'], Decimal('0.00'))
            self.assertEqual(inst['total'], inst['principal'])
        self.assertEqual(sum(i['principal'] for i in schedule['installments']), principal)

    def test_scenario_6_with_interests_flat_and_reducing(self):
        """6. Préstamo con intereses: FLAT vs AMORTIZED_REDUCING (amortización francesa)"""
        principal = Decimal('10000000.00')
        rate = Decimal('3.00') # 3% monthly

        # FLAT
        flat = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=rate,
            interest_rate_period='MONTHLY',
            interest_type='FLAT',
            frequency='MONTHLY',
            total_installments=10,
            first_payment_date=datetime.date(2027, 1, 1)
        )
        # 10 months * 3% = 30% of 10,000,000 = 3,000,000 interest
        self.assertEqual(flat['total_interest'], Decimal('3000000.00'))
        self.assertEqual(flat['total_amount'], Decimal('13000000.00'))

        # REDUCING (French amortization)
        reducing = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=rate,
            interest_rate_period='MONTHLY',
            interest_type='AMORTIZED_REDUCING',
            frequency='MONTHLY',
            total_installments=10,
            first_payment_date=datetime.date(2027, 1, 1)
        )
        # In reducing balance, total interest is strictly less than flat interest
        self.assertLess(reducing['total_interest'], flat['total_interest'])
        self.assertEqual(reducing['installments'][-1]['balance_after'], Decimal('0.00'))
        self.assertEqual(sum(i['principal'] for i in reducing['installments']), principal)

    def test_scenario_7_rounding_adjustment_last_installment(self):
        """7. Préstamo con ajuste de última cuota por redondeo (conservación de centavos/pesos)"""
        # 1,000,000 / 3 = 333,333.333333333...
        principal = Decimal('1000000.00')
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=Decimal('10.00'),
            interest_rate_period='MONTHLY',
            interest_type='FLAT',
            frequency='MONTHLY',
            total_installments=3,
            first_payment_date=datetime.date(2027, 1, 1)
        )

        inst1 = schedule['installments'][0]
        inst2 = schedule['installments'][1]
        inst3 = schedule['installments'][2]

        self.assertEqual(inst1['principal'], Decimal('333333.33'))
        self.assertEqual(inst2['principal'], Decimal('333333.33'))
        # Last installment must absorb the remaining 0.01 to total exactly 1,000,000.00
        self.assertEqual(inst3['principal'], Decimal('333333.34'))

        total_sum_principals = inst1['principal'] + inst2['principal'] + inst3['principal']
        self.assertEqual(total_sum_principals, principal)



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

    def test_loan_delete_requires_confirmation_and_deletes(self):
        loan = LoanCreator.create_loan(
            customer=self.customer,
            principal=Decimal('500000.00'),
            interest_rate=Decimal('2.00'),
            interest_type='FLAT',
            payment_frequency='MONTHLY',
            total_installments=2,
            disbursement_date=datetime.date(2026, 11, 18),
            first_payment_date=datetime.date(2026, 12, 18),
            user=self.user
        )
        loan_id = loan.pk
        loan_code = loan.loan_code

        # 1. GET request: renders confirmation page with warning
        res_get = self.client.get(reverse('loans:delete', kwargs={'pk': loan_id}))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "Confirmación Obligatoria")
        self.assertContains(res_get, loan_code)
        self.assertContains(res_get, "Beatriz Pinzón")
        self.assertContains(res_get, "Sí, Eliminar Préstamo Definitivamente")

        # 2. POST request: executes deletion
        res_post = self.client.post(reverse('loans:delete', kwargs={'pk': loan_id}))
        self.assertEqual(res_post.status_code, 302)
        self.assertRedirects(res_post, reverse('loans:list'))

        # Verify loan and installments are gone
        self.assertFalse(Loan.objects.filter(pk=loan_id).exists())
        self.assertEqual(Installment.objects.filter(loan_id=loan_id).count(), 0)
        self.assertFalse(CashMovement.objects.filter(loan_reference=loan_code).exists())

    def test_loan_create_view_with_disbursement_voucher(self):
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(buf, format='PNG')
        png_bytes = buf.getvalue()

        voucher = SimpleUploadedFile(
            name='desembolso_voucher.png',
            content=png_bytes,
            content_type='image/png'
        )

        post_data = {
            'customer': self.customer.pk,
            'principal': '1500000',
            'interest_rate': '10',
            'interest_type': 'FLAT',
            'payment_frequency': 'MONTHLY',
            'total_installments': '3',
            'disbursement_date': datetime.date.today().strftime('%Y-%m-%d'),
            'first_payment_date': (datetime.date.today() + datetime.timedelta(days=30)).strftime('%Y-%m-%d'),
            'disbursement_voucher': voucher,
            'notes': 'Desembolso con comprobante adjunto'
        }

        res = self.client.post(reverse('loans:create'), data=post_data)
        self.assertEqual(res.status_code, 302)

        loan = Loan.objects.filter(customer=self.customer, notes='Desembolso con comprobante adjunto').first()
        self.assertIsNotNone(loan)
        self.assertTrue(bool(loan.disbursement_voucher))
        self.assertIn('desembolso_voucher', loan.disbursement_voucher.name)

        # Check detail view
        detail_res = self.client.get(reverse('loans:detail', kwargs={'pk': loan.pk}))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, loan.disbursement_voucher.url)
        self.assertContains(detail_res, "Comprobante de Desembolso")


