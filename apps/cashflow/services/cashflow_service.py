import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cashflow.models import CashAccount, CashMovement, CashReconciliation

class CashflowService:
    """
    Business logic and financial services for Cashflow, Accounts (Nequi, Nu, Efectivo),
    Internal Transfers, and Box Reconciliation / Arqueos.
    """

    @classmethod
    def record_manual_movement(
        cls,
        account: CashAccount,
        movement_type: str,
        amount: Decimal,
        movement_date=None,
        description: str = '',
        user=None
    ) -> CashMovement:
        """
        Records a manual non-loan cash movement (Capital injection, Operational expense, or Owner withdrawal).
        """
        if movement_date is None:
            movement_date = timezone.localdate()

        amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if amount <= Decimal('0.00'):
            raise ValidationError("El monto del movimiento debe ser un valor positivo mayor a cero.")

        valid_types = [
            CashMovement.MovementType.CAPITAL_INJECTION,
            CashMovement.MovementType.EXPENSE,
            CashMovement.MovementType.WITHDRAWAL,
        ]
        if movement_type not in valid_types:
            raise ValidationError("Tipo de movimiento manual no permitido.")

        return CashMovement.objects.create(
            account=account,
            movement_type=movement_type,
            amount=amount,
            movement_date=movement_date,
            description=description.strip() or f"{dict(CashMovement.MovementType.choices).get(movement_type)} en {account.name}",
            created_by=user
        )

    @classmethod
    def record_account_transfer(
        cls,
        source_account: CashAccount,
        target_account: CashAccount,
        amount: Decimal,
        transfer_date=None,
        notes: str = '',
        user=None
    ) -> tuple[CashMovement, CashMovement]:
        """
        Executes an atomic transfer between two financial accounts / pockets
        (e.g. from Nequi to Nu, or from Nu to Efectivo).
        """
        if transfer_date is None:
            transfer_date = timezone.localdate()

        if source_account.id == target_account.id:
            raise ValidationError("La cuenta de origen y destino no pueden ser la misma.")

        amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if amount <= Decimal('0.00'):
            raise ValidationError("El monto de transferencia debe ser superior a cero.")

        with transaction.atomic():
            source_acc_locked = CashAccount.objects.select_for_update().get(id=source_account.id)
            target_acc_locked = CashAccount.objects.select_for_update().get(id=target_account.id)

            source_balance = source_acc_locked.get_current_balance()
            if amount > source_balance:
                raise ValidationError(
                    f"Fondos insuficientes en '{source_acc_locked.name}'. "
                    f"Saldo disponible: $ {source_balance:,.0f} COP."
                )

            transfer_ref = f"TRF-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            extra_notes = f" ({notes.strip()})" if notes and notes.strip() else ""

            # Outflow from source
            outflow = CashMovement.objects.create(
                account=source_acc_locked,
                movement_type=CashMovement.MovementType.TRANSFER_OUT,
                amount=amount,
                movement_date=transfer_date,
                description=f"Transferencia enviada a {target_acc_locked.name}{extra_notes}",
                transfer_reference=transfer_ref,
                created_by=user
            )

            # Inflow into target
            inflow = CashMovement.objects.create(
                account=target_acc_locked,
                movement_type=CashMovement.MovementType.TRANSFER_IN,
                amount=amount,
                movement_date=transfer_date,
                description=f"Transferencia recibida desde {source_acc_locked.name}{extra_notes}",
                transfer_reference=transfer_ref,
                created_by=user
            )

            return outflow, inflow

    @classmethod
    def record_reconciliation(
        cls,
        account: CashAccount,
        physical_balance: Decimal,
        notes: str = '',
        user=None,
        adjust_balance: bool = True
    ) -> CashReconciliation:
        """
        Performs box/account reconciliation, comparing actual counted money / app balance
        against the expected system ledger balance, and automatically adjusts the ledger
        balance so that the account balance matches the physical counted balance.
        """
        physical_balance = Decimal(str(physical_balance)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        with transaction.atomic():
            account_locked = CashAccount.objects.select_for_update().get(id=account.id)
            expected_balance = account_locked.get_current_balance()
            difference = physical_balance - expected_balance

            reconciliation = CashReconciliation.objects.create(
                account=account_locked,
                reconciliation_date=timezone.localdate(),
                expected_balance=expected_balance,
                physical_balance=physical_balance,
                difference=difference,
                notes=notes.strip() if notes else '',
                created_by=user
            )

            if adjust_balance and difference != Decimal('0.00'):
                note_text = f" ({notes.strip()})" if notes and notes.strip() else ""
                if difference < Decimal('0.00'):
                    # Faltante / Retiro: salida para ajustar al dinero físico real
                    CashMovement.objects.create(
                        account=account_locked,
                        movement_type=CashMovement.MovementType.WITHDRAWAL,
                        amount=abs(difference),
                        movement_date=timezone.localdate(),
                        description=f"Ajuste por arqueo de caja (Faltante / Retiro){note_text}",
                        transfer_reference=f"ARQ-{reconciliation.id}",
                        created_by=user
                    )
                else:
                    # Sobrante / Ingreso: entrada para ajustar al dinero físico real
                    CashMovement.objects.create(
                        account=account_locked,
                        movement_type=CashMovement.MovementType.CAPITAL_INJECTION,
                        amount=difference,
                        movement_date=timezone.localdate(),
                        description=f"Ajuste por arqueo de caja (Sobrante / Ingreso){note_text}",
                        transfer_reference=f"ARQ-{reconciliation.id}",
                        created_by=user
                    )

            return reconciliation

    @classmethod
    def get_accounts_summary(cls) -> dict:
        """
        Retrieves all active financial accounts with their balances,
        and computes consolidated liquid cash.
        """
        CashAccount.ensure_default_accounts()
        accounts = list(CashAccount.objects.filter(is_active=True).order_by('name'))

        total_consolidated = Decimal('0.00')
        account_cards = []

        for acc in accounts:
            bal = acc.get_current_balance()
            total_consolidated += bal
            account_cards.append({
                'account': acc,
                'balance': bal,
            })

        return {
            'accounts': account_cards,
            'total_consolidated': total_consolidated,
        }

