from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel

class CashAccount(BaseModel):
    """
    Financial Account or Pocket (Bolsillo).
    Represents where money is physically or digitally kept:
    Efectivo en mano, Nequi, Cuenta Nu (Nubank), Daviplata, Bancolombia, etc.
    """
    class AccountType(models.TextChoices):
        CASH = 'CASH', 'Efectivo en Mano / Caja'
        NEQUI = 'NEQUI', 'Nequi'
        NU = 'NU', 'Cuenta Nu (Nubank)'
        DAVIPLATA = 'DAVIPLATA', 'Daviplata'
        BANCOLOMBIA = 'BANCOLOMBIA', 'Bancolombia'
        BANK = 'BANK', 'Otra Cuenta Bancaria'
        OTHER = 'OTHER', 'Otro Bolsillo'

    name = models.CharField(
        max_length=60,
        verbose_name="Nombre de la cuenta o bolsillo"
    )
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.CASH,
        verbose_name="Tipo de cuenta"
    )
    account_number = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        verbose_name="Número de cuenta o celular asociado"
    )
    initial_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Saldo inicial (COP)"
    )
    color = models.CharField(
        max_length=20,
        default='emerald',
        verbose_name="Tema de color"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )

    class Meta:
        verbose_name = "Cuenta / Bolsillo Financiero"
        verbose_name_plural = "Cuentas y Bolsillos Financieros"
        ordering = ['name']

    def __str__(self):
        acc_num = f" ({self.account_number})" if self.account_number else ""
        return f"{self.name}{acc_num}"

    def get_current_balance(self) -> Decimal:
        """
        Calculates liquid balance of this specific account / pocket.
        Initial balance + inflows - outflows.
        """
        inflows = self.movements.filter(
            movement_type__in=[
                CashMovement.MovementType.CAPITAL_INJECTION,
                CashMovement.MovementType.PRINCIPAL_RECOVERY,
                CashMovement.MovementType.INTEREST_INCOME,
                CashMovement.MovementType.TRANSFER_IN,
            ],
            is_active=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        outflows = self.movements.filter(
            movement_type__in=[
                CashMovement.MovementType.LOAN_DISBURSEMENT,
                CashMovement.MovementType.EXPENSE,
                CashMovement.MovementType.WITHDRAWAL,
                CashMovement.MovementType.REVERSAL,
                CashMovement.MovementType.TRANSFER_OUT,
            ],
            is_active=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        return self.initial_balance + inflows - outflows

    @classmethod
    def ensure_default_accounts(cls):
        """
        Ensures default essential pockets exist in the system:
        Efectivo, Nequi, Nu Colombia, Bancolombia.
        """
        defaults = [
            {'name': 'Efectivo en Mano / Billetera', 'account_type': cls.AccountType.CASH, 'color': 'emerald'},
            {'name': 'Nequi', 'account_type': cls.AccountType.NEQUI, 'color': 'purple'},
            {'name': 'Cuenta Nu (Nubank)', 'account_type': cls.AccountType.NU, 'color': 'fuchsia'},
            {'name': 'Bancolombia', 'account_type': cls.AccountType.BANCOLOMBIA, 'color': 'amber'},
        ]
        created_accounts = []
        for d in defaults:
            account, _ = cls.objects.get_or_create(
                name=d['name'],
                defaults={
                    'account_type': d['account_type'],
                    'color': d['color'],
                    'initial_balance': Decimal('0.00')
                }
            )
            created_accounts.append(account)
        return created_accounts

    @classmethod
    def get_default_account(cls, account_type=None):
        """Returns or creates the primary default account."""
        cls.ensure_default_accounts()
        if account_type:
            account = cls.objects.filter(account_type=account_type, is_active=True).first()
            if account:
                return account
        return cls.objects.filter(account_type=cls.AccountType.CASH, is_active=True).first() or cls.objects.first()


class CashMovement(BaseModel):
    """
    Cash movement entity tracking real money flow (inflows, outflows,
    loan disbursements, repayments, operational expenses, capital injections,
    and transfers between pockets: Nequi, Nu, Efectivo).
    """
    class MovementType(models.TextChoices):
        CAPITAL_INJECTION = 'CAPITAL_INJECTION', 'Aporte de Capital (+)'
        LOAN_DISBURSEMENT = 'LOAN_DISBURSEMENT', 'Desembolso de Préstamo (-)'
        PRINCIPAL_RECOVERY = 'PRINCIPAL_RECOVERY', 'Recuperación de Capital (+)'
        INTEREST_INCOME = 'INTEREST_INCOME', 'Cobro de Intereses (+)'
        EXPENSE = 'EXPENSE', 'Gasto Operativo (-)'
        WITHDRAWAL = 'WITHDRAWAL', 'Retiro de Dinero (-)'
        REVERSAL = 'REVERSAL', 'Reversión Contable (-)'
        TRANSFER_IN = 'TRANSFER_IN', 'Transferencia Recibida (+)'
        TRANSFER_OUT = 'TRANSFER_OUT', 'Transferencia Enviada (-)'

    account = models.ForeignKey(
        CashAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name="Cuenta o Bolsillo"
    )
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
    
    # Generic references to loan, payment, or transfer without circular dependencies
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
    transfer_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Identificador de transferencia"
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
        acc = f" [{self.account.name}]" if self.account else ""
        return f"{self.get_movement_type_display()}{acc} — $ {self.amount:,.0f} ({self.movement_date})"

    @property
    def is_inflow(self) -> bool:
        """Determines if the transaction increases cash balance."""
        return self.movement_type in [
            self.MovementType.CAPITAL_INJECTION,
            self.MovementType.PRINCIPAL_RECOVERY,
            self.MovementType.INTEREST_INCOME,
            self.MovementType.TRANSFER_IN,
        ]

    @property
    def signed_amount(self) -> Decimal:
        """Returns signed amount (+ for inflow, - for outflow)."""
        return self.amount if self.is_inflow else -self.amount

    @classmethod
    def get_current_balance(cls) -> Decimal:
        """
        Calculates total consolidated liquid cash currently available across ALL accounts,
        summing all inflows and subtracting all outflows.
        """
        inflows = cls.objects.filter(
            movement_type__in=[
                cls.MovementType.CAPITAL_INJECTION,
                cls.MovementType.PRINCIPAL_RECOVERY,
                cls.MovementType.INTEREST_INCOME,
                cls.MovementType.TRANSFER_IN,
            ],
            is_active=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        outflows = cls.objects.filter(
            movement_type__in=[
                cls.MovementType.LOAN_DISBURSEMENT,
                cls.MovementType.EXPENSE,
                cls.MovementType.WITHDRAWAL,
                cls.MovementType.REVERSAL,
                cls.MovementType.TRANSFER_OUT,
            ],
            is_active=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        # Add initial balances from any registered accounts
        initial_sum = CashAccount.objects.filter(is_active=True).aggregate(
            total=models.Sum('initial_balance')
        )['total'] or Decimal('0.00')

        return initial_sum + inflows - outflows


class CashReconciliation(BaseModel):
    """
    Arqueo y Conciliación de Caja / Cuentas.
    Compares the calculated system balance with actual counted physical cash
    or balance in banking apps (Nequi, Nu, etc.).
    """
    account = models.ForeignKey(
        CashAccount,
        on_delete=models.PROTECT,
        related_name='reconciliations',
        verbose_name="Cuenta o Bolsillo Conciliado"
    )
    reconciliation_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Fecha del arqueo"
    )
    expected_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Saldo en sistema (COP)"
    )
    physical_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Saldo físico / app contado (COP)"
    )
    difference = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Diferencia (Sobrante / Faltante)"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones / Justificación de descuadre"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciliations',
        verbose_name="Realizado por"
    )

    class Meta:
        verbose_name = "Arqueo / Conciliación"
        verbose_name_plural = "Arqueos y Conciliaciones"
        ordering = ['-reconciliation_date', '-created_at']

    def __str__(self):
        status = "Cuadrado" if self.difference == 0 else ("Sobrante" if self.difference > 0 else "Faltante")
        return f"Arqueo {self.account.name} ({self.reconciliation_date}) — {status}: $ {abs(self.difference):,.0f}"
