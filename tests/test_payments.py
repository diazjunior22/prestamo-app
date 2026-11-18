import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.cashflow.models import CashMovement
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services.payment_allocator import allocate_payment
from apps.payments.services.payment_reverser import reverse_payment
from apps.payments.services.receipt_generator import build_receipt_pdf_bytes

User = get_user_model()

class PaymentModuleTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            email='admin@test.local',
            username='admin_test',
            password='Password123!',
            first_name='Admin',
            last_name='Tester'
        )
        self.client.login(email='admin@test.local', password='Password123!')

        self.customer = Customer.objects.create(
            first_name='Carlos',
            last_name='Mendoza',
            document_type=Customer.DocumentType.CC,
            document_number='1020304050',
            phone='3001234567',
            whatsapp='3001234567',
            city='Bogotá'
        )

        # Create a loan: $1,200,000 at 10% flat, 3 monthly installments = total $1,320,000 (total interest $120,000)
        # Each installment: total $440,000 (interest $40,000, principal $400,000)
        today = timezone.localdate()
        self.loan = Loan.objects.create(
            customer=self.customer,
            loan_code='LN-202611-TEST',
            principal=Decimal('1200000.00'),
            interest_rate=Decimal('10.00'),
            interest_type=Loan.InterestType.FLAT,
            payment_frequency=Loan.PaymentFrequency.MONTHLY,
            total_installments=3,
            disbursement_date=today,
            first_payment_date=today + datetime.timedelta(days=30),
            total_interest=Decimal('120000.00'),
            total_amount=Decimal('1320000.00'),
            paid_principal=Decimal('0.00'),
            paid_interest=Decimal('0.00'),
            balance=Decimal('1320000.00'),
            status=Loan.Status.ACTIVE,
            created_by=self.user
        )

        # Create 3 installments
        self.inst1 = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=1,
            due_date=today + datetime.timedelta(days=30),
            principal_amount=Decimal('400000.00'),
            interest_amount=Decimal('40000.00'),
            total_amount=Decimal('440000.00'),
            balance=Decimal('440000.00'),
            status=Installment.Status.PENDING
        )
        self.inst2 = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=2,
            due_date=today + datetime.timedelta(days=60),
            principal_amount=Decimal('400000.00'),
            interest_amount=Decimal('40000.00'),
            total_amount=Decimal('440000.00'),
            balance=Decimal('440000.00'),
            status=Installment.Status.PENDING
        )
        self.inst3 = Installment.objects.create(
            loan=self.loan,
            customer=self.customer,
            installment_number=3,
            due_date=today + datetime.timedelta(days=90),
            principal_amount=Decimal('400000.00'),
            interest_amount=Decimal('40000.00'),
            total_amount=Decimal('440000.00'),
            balance=Decimal('440000.00'),
            status=Installment.Status.PENDING
        )

    def test_waterfall_allocation_partial_and_multi_installment(self):
        """
        Payment of $500,000 should completely pay Installment 1 ($440,000)
        and partially pay Installment 2 ($60,000: $40,000 interest + $20,000 principal).
        """
        payment = allocate_payment(
            loan=self.loan,
            amount=Decimal('500000.00'),
            payment_date=timezone.localdate(),
            payment_method=Payment.PaymentMethod.NEQUI,
            reference_number='TRX-123456',
            user=self.user
        )

        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertEqual(payment.amount, Decimal('500000.00'))

        # Check Installment 1: fully paid
        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.status, Installment.Status.PAID)
        self.assertEqual(self.inst1.paid_interest, Decimal('40000.00'))
        self.assertEqual(self.inst1.paid_principal, Decimal('400000.00'))
        self.assertEqual(self.inst1.balance, Decimal('0.00'))

        # Check Installment 2: partially paid (interest first: $40,000, then principal: $20,000)
        self.inst2.refresh_from_db()
        self.assertEqual(self.inst2.status, Installment.Status.PARTIAL)
        self.assertEqual(self.inst2.paid_interest, Decimal('40000.00'))
        self.assertEqual(self.inst2.paid_principal, Decimal('20000.00'))
        self.assertEqual(self.inst2.balance, Decimal('380000.00'))

        # Check Installment 3: untouched
        self.inst3.refresh_from_db()
        self.assertEqual(self.inst3.status, Installment.Status.PENDING)
        self.assertEqual(self.inst3.balance, Decimal('440000.00'))

        # Check Loan totals
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.paid_interest, Decimal('80000.00'))
        self.assertEqual(self.loan.paid_principal, Decimal('420000.00'))
        self.assertEqual(self.loan.balance, Decimal('820000.00'))
        self.assertEqual(self.loan.status, Loan.Status.ACTIVE)

        # Check Cash Movements created
        cash_recovery = CashMovement.objects.filter(movement_type=CashMovement.MovementType.PRINCIPAL_RECOVERY).first()
        self.assertIsNotNone(cash_recovery)
        self.assertEqual(cash_recovery.amount, Decimal('420000.00'))

        cash_interest = CashMovement.objects.filter(movement_type=CashMovement.MovementType.INTEREST_INCOME).first()
        self.assertIsNotNone(cash_interest)
        self.assertEqual(cash_interest.amount, Decimal('80000.00'))

        # Check Cash ledger balance increases by $500,000
        self.assertEqual(CashMovement.get_current_balance(), Decimal('500000.00'))

    def test_full_loan_payoff(self):
        """
        Paying full loan balance ($1,320,000) should mark all installments
        and the loan as PAID.
        """
        payment = allocate_payment(
            loan=self.loan,
            amount=Decimal('1320000.00'),
            payment_date=timezone.localdate(),
            payment_method=Payment.PaymentMethod.CASH,
            user=self.user
        )

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.balance, Decimal('0.00'))
        self.assertEqual(self.loan.status, Loan.Status.PAID)

        for inst in [self.inst1, self.inst2, self.inst3]:
            inst.refresh_from_db()
            self.assertEqual(inst.status, Installment.Status.PAID)
            self.assertEqual(inst.balance, Decimal('0.00'))

    def test_overpayment_validation(self):
        """Cannot pay more than remaining loan balance."""
        with self.assertRaises(ValidationError):
            allocate_payment(
                loan=self.loan,
                amount=Decimal('1500000.00'),
                payment_date=timezone.localdate(),
                user=self.user
            )

    def test_reversal_restores_balances_and_records_cash_outflow(self):
        """
        Reversing a payment must restore all affected installments and loan balances,
        and create an offsetting REVERSAL entry in CashMovement.
        """
        payment = allocate_payment(
            loan=self.loan,
            amount=Decimal('440000.00'),
            payment_date=timezone.localdate(),
            user=self.user
        )

        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.status, Installment.Status.PAID)
        self.assertEqual(CashMovement.get_current_balance(), Decimal('440000.00'))

        # Now reverse the payment
        reversed_payment = reverse_payment(
            payment=payment,
            reversal_reason='Cheque sin fondos devuelto por el banco',
            user=self.user
        )

        self.assertTrue(reversed_payment.is_reversed)
        self.assertEqual(reversed_payment.reversal_reason, 'Cheque sin fondos devuelto por el banco')

        # Installment 1 restored
        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.balance, Decimal('440000.00'))
        self.assertEqual(self.inst1.status, Installment.Status.PENDING)
        self.assertIsNone(self.inst1.paid_at)

        # Loan restored
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.balance, Decimal('1320000.00'))
        self.assertEqual(self.loan.paid_principal, Decimal('0.00'))
        self.assertEqual(self.loan.paid_interest, Decimal('0.00'))

        # Net cash balance is now $0 (inflows $440,000 - outflow reversal $440,000)
        self.assertEqual(CashMovement.get_current_balance(), Decimal('0.00'))

        # Reversing again should fail
        with self.assertRaises(ValidationError):
            reverse_payment(payment, reversal_reason='Otro intento', user=self.user)

    def test_pdf_receipt_generation(self):
        """Test PDF receipt generator produces valid PDF bytes."""
        payment = allocate_payment(
            loan=self.loan,
            amount=Decimal('200000.00'),
            payment_date=timezone.localdate(),
            user=self.user,
            auto_generate_pdf=False  # Test generator directly
        )
        pdf_bytes = build_receipt_pdf_bytes(payment)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_views_payment_flow(self):
        """Test HTTP responses for payments views."""
        # 1. List view
        response = self.client.get(reverse('payments:list'))
        self.assertEqual(response.status_code, 200)

        # 2. Loan info HTMX endpoint
        response = self.client.get(reverse('payments:loan_info', kwargs={'loan_id': self.loan.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.loan.loan_code)

        # 3. Create view GET
        response = self.client.get(reverse('payments:create') + f'?loan={self.loan.id}')
        self.assertEqual(response.status_code, 200)

        # 4. Create view POST
        post_data = {
            'loan': self.loan.id,
            'amount': '440000.00',
            'payment_date': timezone.localdate().strftime('%Y-%m-%d'),
            'payment_method': 'NEQUI',
            'reference_number': 'TEST-REC-101',
            'notes': 'Pago mensual vía Nequi'
        }
        response = self.client.post(reverse('payments:create'), data=post_data)
        self.assertEqual(response.status_code, 302)

        payment = Payment.objects.filter(reference_number='TEST-REC-101').first()
        self.assertIsNotNone(payment)

        # 5. Detail view
        response = self.client.get(reverse('payments:detail', kwargs={'payment_id': payment.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, payment.receipt_number)

        # 6. PDF Receipt endpoint
        response = self.client.get(reverse('payments:receipt_pdf', kwargs={'payment_id': payment.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # 7. Reverse payment view
        response = self.client.post(
            reverse('payments:reverse', kwargs={'payment_id': payment.id}),
            data={'reversal_reason': 'Error de digitación en el comprobante'}
        )
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertTrue(payment.is_reversed)

