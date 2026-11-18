import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.customers.models import Customer

class Loan(BaseModel):
    """
    Loan contract representing disbursed capital, terms, interest scheme,
    amortization type, and balance tracking.
    """
    class InterestType(models.TextChoices):
        FLAT = 'FLAT', 'Interés Fijo sobre Capital Inicial'
        AMORTIZED_REDUCING = 'AMORTIZED_REDUCING', 'Interés sobre Saldo Pendiente (Sistema Francés)'
        NO_INTEREST = 'NO_INTEREST', 'Sin Intereses (0%)'

    class PaymentFrequency(models.TextChoices):
        DAILY = 'DAILY', 'Diario'
        WEEKLY = 'WEEKLY', 'Semanal'
        BIWEEKLY = 'BIWEEKLY', 'Quincenal'
        MONTHLY = 'MONTHLY', 'Mensual'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Activo'
        PAID = 'PAID', 'Finalizado (Totalmente Pagado)'
        OVERDUE = 'OVERDUE', 'En Mora'
        CANCELLED = 'CANCELLED', 'Anulado'
        REFINANCED = 'REFINANCED', 'Refinanciado'

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='loans',
        verbose_name="Cliente prestatario"
    )
    loan_code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name="Código de préstamo"
    )
    principal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Capital desembolsado (COP)"
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Tasa de interés (%)"
    )
    interest_type = models.CharField(
        max_length=25,
        choices=InterestType.choices,
        default=InterestType.FLAT,
        verbose_name="Modalidad de interés"
    )
    payment_frequency = models.CharField(
        max_length=20,
        choices=PaymentFrequency.choices,
        default=PaymentFrequency.MONTHLY,
        verbose_name="Frecuencia de pago"
    )
    total_installments = models.PositiveIntegerField(
        verbose_name="Número de cuotas"
    )
    disbursement_date = models.DateField(
        verbose_name="Fecha de desembolso"
    )
    first_payment_date = models.DateField(
        verbose_name="Fecha de primer vencimiento"
    )
    
    # Financial Totals & Balances
    total_interest = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Total intereses pactados"
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Total a pagar (Capital + Intereses)"
    )
    paid_principal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Capital amortizado"
    )
    paid_interest = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Intereses recaudados"
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Saldo total pendiente"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name="Estado del préstamo"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones del préstamo"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_loans',
        verbose_name="Creado por"
    )

    class Meta:
        verbose_name = "Préstamo"
        verbose_name_plural = "Préstamos"
        ordering = ['-disbursement_date', '-created_at']

    def __str__(self):
        return f"{self.loan_code} — {self.customer.full_name} (${self.principal:,.0f} COP)"

    @property
    def total_paid(self) -> Decimal:
        return self.paid_principal + self.paid_interest

    @property
    def progress_percentage(self) -> float:
        if self.total_amount > Decimal('0.00'):
            return float((self.total_paid / self.total_amount) * 100)
        return 0.0

    @property
    def paid_installments_count(self) -> int:
        return self.installments.filter(status=Installment.Status.PAID).count()

    @property
    def overdue_installments_count(self) -> int:
        return self.installments.filter(status=Installment.Status.OVERDUE).count()


class Installment(BaseModel):
    """
    Persistent installment representing a single scheduled payment obligation.
    Stores assigned principal, assigned interest, paid portions, and remaining balance.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        PARTIAL = 'PARTIAL', 'Abono Parcial'
        PAID = 'PAID', 'Pagada'
        OVERDUE = 'OVERDUE', 'Vencida'
        CANCELLED = 'CANCELLED', 'Anulada'

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name='installments',
        verbose_name="Préstamo"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='installments',
        verbose_name="Cliente"
    )
    installment_number = models.PositiveIntegerField(
        verbose_name="Número de cuota"
    )
    due_date = models.DateField(
        db_index=True,
        verbose_name="Fecha de vencimiento"
    )
    principal_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Capital asignado"
    )
    interest_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Interés asignado"
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor total de cuota"
    )
    paid_principal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Capital pagado"
    )
    paid_interest = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Interés pagado"
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Saldo pendiente de la cuota"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Estado de cuota"
    )
    paid_at = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de pago total"
    )

    class Meta:
        verbose_name = "Cuota"
        verbose_name_plural = "Cuotas"
        ordering = ['loan', 'installment_number']
        unique_together = ('loan', 'installment_number')
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['status']),
            models.Index(fields=['loan', 'status']),
        ]

    def __str__(self):
        return f"{self.loan.loan_code} — Cuota #{self.installment_number} (${self.total_amount:,.0f} COP)"

    @property
    def total_paid(self) -> Decimal:
        return self.paid_principal + self.paid_interest

