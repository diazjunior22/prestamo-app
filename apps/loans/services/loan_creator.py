import random
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.cashflow.models import CashMovement
from .loan_calculator import LoanCalculator

class LoanCreator:
    """
    Service responsible for atomic loan origination and disbursement.
    Executes in a single database transaction:
    1. Generates unique loan code.
    2. Calculates verified amortization schedule.
    3. Persists Loan record.
    4. Generates all Installment records.
    5. Registers CashMovement outflow (LOAN_DISBURSEMENT).
    """

    @staticmethod
    def generate_loan_code() -> str:
        """Generates human-readable, unique loan code like LN-202611-8492."""
        now = timezone.localdate()
        prefix = f"LN-{now.strftime('%Y%m')}"
        while True:
            suffix = f"{random.randint(1000, 9999)}"
            code = f"{prefix}-{suffix}"
            if not Loan.objects.filter(loan_code=code).exists():
                return code

    @classmethod
    def create_loan(
        cls,
        customer: Customer,
        principal: Decimal,
        interest_rate: Decimal,
        interest_type: str,
        payment_frequency: str,
        total_installments: int,
        disbursement_date,
        first_payment_date,
        notes: str = "",
        user=None
    ) -> Loan:
        """
        Executes atomic creation of Loan, Installments, and Cash Movement.
        """
        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=interest_rate,
            interest_type=interest_type,
            frequency=payment_frequency,
            total_installments=total_installments,
            first_payment_date=first_payment_date
        )

        with transaction.atomic():
            loan_code = cls.generate_loan_code()

            loan = Loan.objects.create(
                customer=customer,
                loan_code=loan_code,
                principal=schedule['principal'],
                interest_rate=schedule['interest_rate'],
                interest_type=schedule['interest_type'],
                payment_frequency=schedule['frequency'],
                total_installments=schedule['total_installments'],
                disbursement_date=disbursement_date,
                first_payment_date=first_payment_date,
                total_interest=schedule['total_interest'],
                total_amount=schedule['total_amount'],
                paid_principal=Decimal('0.00'),
                paid_interest=Decimal('0.00'),
                balance=schedule['total_amount'],
                status=Loan.Status.ACTIVE,
                notes=notes,
                created_by=user
            )

            # Bulk create installments
            installments_to_create = []
            for item in schedule['installments']:
                installments_to_create.append(Installment(
                    loan=loan,
                    customer=customer,
                    installment_number=item['installment_number'],
                    due_date=item['due_date'],
                    principal_amount=item['principal'],
                    interest_amount=item['interest'],
                    total_amount=item['total'],
                    paid_principal=Decimal('0.00'),
                    paid_interest=Decimal('0.00'),
                    balance=item['total'],
                    status=Installment.Status.PENDING
                ))

            Installment.objects.bulk_create(installments_to_create)

            # Record Cash Outflow (Loan Disbursement)
            CashMovement.objects.create(
                movement_type=CashMovement.MovementType.LOAN_DISBURSEMENT,
                amount=schedule['principal'],
                movement_date=disbursement_date,
                description=f"Desembolso préstamo {loan.loan_code} a {customer.full_name}",
                loan_reference=loan.loan_code,
                created_by=user
            )

            return loan

