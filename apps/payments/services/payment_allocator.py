from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.loans.models import Loan, Installment
from apps.cashflow.models import CashMovement
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services.receipt_generator import generate_and_save_receipt_pdf

def allocate_payment(
    loan: Loan,
    amount: Decimal,
    payment_date=None,
    payment_method: str = Payment.PaymentMethod.CASH,
    reference_number: str = '',
    notes: str = '',
    user=None,
    auto_generate_pdf: bool = True
) -> Payment:
    """
    Executes atomic payment allocation using waterfall imputation.
    Allocates funds sequentially to the oldest unpaid/partial installments:
    1. Satisfies accrued interest first.
    2. Satisfies principal balance second.
    Updates Installments, Loan balances and status, creates CashMovements,
    and generates the PDF receipt.
    """
    if payment_date is None:
        payment_date = timezone.localdate()

    amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    if amount <= Decimal('0.00'):
        raise ValidationError("El monto a abonar debe ser un valor positivo mayor a cero.")

    with transaction.atomic():
        # Lock loan record for concurrency safety
        loan_locked = Loan.objects.select_for_update().get(id=loan.id)

        if loan_locked.status in [Loan.Status.PAID, Loan.Status.CANCELLED]:
            raise ValidationError(
                f"El préstamo {loan_locked.loan_code} está en estado '{loan_locked.get_status_display()}' "
                "y no admite nuevos abonos."
            )

        if amount > loan_locked.balance:
            raise ValidationError(
                f"El monto a pagar ($ {amount:,.2f}) no puede superar el saldo pendiente del préstamo "
                f"($ {loan_locked.balance:,.2f})."
            )

        # Generate unique receipt sequence
        receipt_number = Payment.generate_receipt_number()

        # Create Payment entity
        payment = Payment.objects.create(
            loan=loan_locked,
            customer=loan_locked.customer,
            receipt_number=receipt_number,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number.strip() if reference_number else '',
            status=Payment.Status.COMPLETED,
            notes=notes.strip() if notes else '',
            created_by=user
        )

        # Select unpaid or partially paid installments ordered by sequence
        installments = list(
            Installment.objects.select_for_update().filter(
                loan=loan_locked,
                status__in=[
                    Installment.Status.PENDING,
                    Installment.Status.PARTIAL,
                    Installment.Status.OVERDUE,
                ]
            ).order_by('installment_number')
        )

        remaining_cash = amount
        total_principal_applied = Decimal('0.00')
        total_interest_applied = Decimal('0.00')

        for inst in installments:
            if remaining_cash <= Decimal('0.00'):
                break

            pending_interest = max(Decimal('0.00'), inst.interest_amount - inst.paid_interest)
            pending_principal = max(Decimal('0.00'), inst.principal_amount - inst.paid_principal)

            # 1. Apply to interest first
            interest_applied = min(remaining_cash, pending_interest)
            remaining_cash -= interest_applied

            # 2. Apply to principal second
            principal_applied = min(remaining_cash, pending_principal)
            remaining_cash -= principal_applied

            inst_applied = interest_applied + principal_applied

            if inst_applied > Decimal('0.00'):
                inst.paid_interest += interest_applied
                inst.paid_principal += principal_applied
                inst.balance = inst.total_amount - (inst.paid_interest + inst.paid_principal)

                if inst.balance <= Decimal('0.00'):
                    inst.balance = Decimal('0.00')
                    inst.status = Installment.Status.PAID
                    inst.paid_at = payment_date
                else:
                    inst.status = Installment.Status.PARTIAL

                inst.save()

                PaymentAllocation.objects.create(
                    payment=payment,
                    installment=inst,
                    principal_applied=principal_applied,
                    interest_applied=interest_applied,
                    total_applied=inst_applied
                )

                total_principal_applied += principal_applied
                total_interest_applied += interest_applied

        # Update loan financial balances
        loan_locked.paid_principal += total_principal_applied
        loan_locked.paid_interest += total_interest_applied
        new_balance = loan_locked.total_amount - (loan_locked.paid_principal + loan_locked.paid_interest)
        loan_locked.balance = max(Decimal('0.00'), new_balance)

        if loan_locked.balance <= Decimal('0.00'):
            loan_locked.balance = Decimal('0.00')
            loan_locked.status = Loan.Status.PAID
        else:
            has_overdue = loan_locked.installments.filter(status=Installment.Status.OVERDUE).exists()
            loan_locked.status = Loan.Status.OVERDUE if has_overdue else Loan.Status.ACTIVE

        loan_locked.save()

        # Record Inflows into CashMovement
        if total_principal_applied > Decimal('0.00'):
            CashMovement.objects.create(
                movement_type=CashMovement.MovementType.PRINCIPAL_RECOVERY,
                amount=total_principal_applied,
                movement_date=payment_date,
                description=f"Recaudo capital recibo {receipt_number} — Préstamo {loan_locked.loan_code} ({loan_locked.customer.full_name})",
                loan_reference=loan_locked.loan_code,
                payment_reference=receipt_number,
                created_by=user
            )

        if total_interest_applied > Decimal('0.00'):
            CashMovement.objects.create(
                movement_type=CashMovement.MovementType.INTEREST_INCOME,
                amount=total_interest_applied,
                movement_date=payment_date,
                description=f"Recaudo intereses recibo {receipt_number} — Préstamo {loan_locked.loan_code} ({loan_locked.customer.full_name})",
                loan_reference=loan_locked.loan_code,
                payment_reference=receipt_number,
                created_by=user
            )

        # Generate official PDF receipt
        if auto_generate_pdf:
            try:
                generate_and_save_receipt_pdf(payment)
            except Exception as e:
                # Log but do not break transaction if font or render warning
                print(f"[Warning] Error generating PDF receipt for {receipt_number}: {e}")

        return payment
