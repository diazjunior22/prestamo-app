from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.loans.models import Loan, Installment
from apps.cashflow.models import CashMovement
from apps.payments.models import Payment
from apps.payments.services.receipt_generator import generate_and_save_receipt_pdf

def reverse_payment(
    payment: Payment,
    reversal_reason: str,
    user=None,
    auto_update_pdf: bool = True
) -> Payment:
    """
    Executes an audited financial reversal of a previously applied Payment.
    1. Reverts installment balances and status transitions.
    2. Restores loan balances and active/overdue state.
    3. Records an offsetting REVERSAL cash movement in the general cash ledger.
    4. Stamps payment as REVERSED with audit trail (user, timestamp, reason).
    5. Updates the PDF receipt with the official REVERSADO watermark.
    """
    if not reversal_reason or len(reversal_reason.strip()) < 5:
        raise ValidationError("Debe proporcionar un motivo de reversión justificado (mínimo 5 caracteres).")

    with transaction.atomic():
        payment_locked = Payment.objects.select_for_update().get(id=payment.id)

        if payment_locked.is_reversed:
            raise ValidationError(f"El recibo {payment_locked.receipt_number} ya ha sido reversado previamente.")

        loan_locked = Loan.objects.select_for_update().get(id=payment_locked.loan_id)
        today = timezone.localdate()

        # Revert allocations on each affected installment
        allocations = list(payment_locked.allocations.select_related('installment'))
        for alloc in allocations:
            inst = Installment.objects.select_for_update().get(id=alloc.installment_id)
            inst.paid_principal -= alloc.principal_applied
            inst.paid_interest -= alloc.interest_applied
            inst.balance = inst.total_amount - (inst.paid_principal + inst.paid_interest)
            inst.paid_at = None

            # Re-evaluate installment status
            if inst.balance >= inst.total_amount:
                inst.balance = inst.total_amount
                inst.status = Installment.Status.OVERDUE if inst.due_date < today else Installment.Status.PENDING
            else:
                inst.status = Installment.Status.OVERDUE if inst.due_date < today else Installment.Status.PARTIAL

            inst.save()

        # Restore loan balances
        loan_locked.paid_principal -= payment_locked.total_principal_applied
        loan_locked.paid_interest -= payment_locked.total_interest_applied
        loan_locked.balance = loan_locked.total_amount - (loan_locked.paid_principal + loan_locked.paid_interest)

        # Restore loan status
        has_overdue = loan_locked.installments.filter(status=Installment.Status.OVERDUE).exists()
        loan_locked.status = Loan.Status.OVERDUE if has_overdue else Loan.Status.ACTIVE
        loan_locked.save()

        # Record offsetting cash ledger entry
        CashMovement.objects.create(
            movement_type=CashMovement.MovementType.REVERSAL,
            amount=payment_locked.amount,
            movement_date=today,
            description=f"Reversión contable {payment_locked.receipt_number}: {reversal_reason.strip()}",
            loan_reference=loan_locked.loan_code,
            payment_reference=payment_locked.receipt_number,
            created_by=user
        )

        # Update Payment record
        payment_locked.status = Payment.Status.REVERSED
        payment_locked.reversal_reason = reversal_reason.strip()
        payment_locked.reversed_at = timezone.now()
        payment_locked.reversed_by = user
        payment_locked.save()

        # Re-generate PDF with REVERSADO marking
        if auto_update_pdf:
            try:
                generate_and_save_receipt_pdf(payment_locked)
            except Exception as e:
                print(f"[Warning] Error updating reversed PDF receipt {payment_locked.receipt_number}: {e}")

        return payment_locked
