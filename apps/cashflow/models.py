from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel

class CashMovement(BaseModel):
    """
    Cash movement entity tracking real money flow (inflows, outflows,
    loan disbursements, repayments, operational expenses and capital injections).
    """
    class MovementType(models.TextChoices):
        CAPITAL_INJECTION = 'CAPITAL_INJECTION', 'Aporte / Capital Inicial (+)'
        LOAN_DISBURSEMENT = 'LOAN_DISBURSEMENT', 'Desembolso de Préstamo (-)'
        PRINCIPAL_RECOVERY = 'PRINCIPAL_RECOVERY', 'Recuperación de Capital (+)'
        INTEREST_INCOME = 'INTEREST_INCOME', 'Cobro de Intereses (+)'
        EXPENSE = 'EXPENSE', 'Gasto Operativo (-)'
        WITHDRAWAL = 'WITHDRAWAL', 'Retiro de Dinero (-)'
        REVERSAL = 'REVERSAL', 'Reversión Contable'

    movement_type = models.CharField(
        max_length=30,
        choices=MovementType.choices,
        db_index=True,
        verbose_name="Tipo de movimiento"
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Monto (COP)"
    )
    movement_date = models.DateField(
        db_index=True,
        verbose_name="Fecha del movimiento"
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Descripción o concepto"
    )
    
    # Generic references to loan and payment without circular dependencies
    loan_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Código de préstamo asociado"
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Número de recibo asociado"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_movements',
        verbose_name="Registrado por"
    )

    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        ordering = ['-movement_date', '-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} — $ {self.amount:,.0f} ({self.movement_date})"

    @property
    def is_inflow(self) -> bool:
        """Determines if the transaction increases cash balance."""
        return self.movement_type in [
            self.MovementType.CAPITAL_INJECTION,
            self.MovementType.PRINCIPAL_RECOVERY,
            self.MovementType.INTEREST_INCOME,
        ]

    @property
    def signed_amount(self) -> Decimal:
        """Returns signed amount (+ for inflow, - for outflow)."""
        return self.amount if self.is_inflow else -self.amount

    @classmethod
    def get_current_balance(cls) -> Decimal:
        """
        Calculates real liquid cash currently available by summing all inflows
        and subtracting all outflows.
        """
        inflows = cls.objects.filter(
            movement_type__in=[
                cls.MovementType.CAPITAL_INJECTION,
                cls.MovementType.PRINCIPAL_RECOVERY,
                cls.MovementType.INTEREST_INCOME,
            ],
            is_active=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        outflows = cls.objects.filter(
            movement_type__in=[
                cls.MovementType.LOAN_DISBURSEMENT,
                cls.MovementType.EXPENSE,
                cls.MovementType.WITHDRAWAL,
                cls.MovementType.REVERSAL,
            ],
            is_active=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        return inflows - outflows

