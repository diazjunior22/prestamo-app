from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.loans.models import Loan, Installment
from apps.customers.models import Customer

class Payment(BaseModel):
    """
    Financial payment / installment record.
    Represents an actual incoming money transaction linked to a loan and customer.
    Distributes funds into installments (waterfall logic) and tracks accounting reversals.
    """
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Efectivo'
        NEQUI = 'NEQUI', 'Nequi'
        DAVIPLATA = 'DAVIPLATA', 'Daviplata'
        BANCOLOMBIA = 'BANCOLOMBIA', 'Bancolombia'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Transferencia Bancaria'
        OTHER = 'OTHER', 'Otro'

    class Status(models.TextChoices):
        COMPLETED = 'COMPLETED', 'Completado'
        REVERSED = 'REVERSED', 'Reversado'

    loan = models.ForeignKey(
        Loan,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Préstamo"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Cliente"
    )
    receipt_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name="Número de recibo"
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Monto del abono (COP)"
    )
    payment_date = models.DateField(
        db_index=True,
        verbose_name="Fecha del pago"
    )
    payment_method = models.CharField(
        max_length=25,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="Método de pago"
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referencia o # de comprobante"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_index=True,
        verbose_name="Estado del pago"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_payments',
        verbose_name="Registrado por"
    )
    receipt_pdf = models.FileField(
        upload_to='receipts/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Comprobante PDF"
    )

    # Reversal tracking audit fields
    reversal_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo de reversión"
    )
    reversed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha y hora de reversión"
    )
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversed_payments',
        verbose_name="Reversado por"
    )

    class Meta:
        verbose_name = "Pago / Abono"
        verbose_name_plural = "Pagos y Abonos"
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['status']),
            models.Index(fields=['loan', 'status']),
            models.Index(fields=['customer', 'status']),
        ]

    def __str__(self):
        return f"{self.receipt_number} — {self.customer.full_name} (${self.amount:,.0f} COP)"

    @classmethod
    def generate_receipt_number(cls) -> str:
        """
        Generates consecutive unique receipt code, format: REC-YYYYMM-XXXX
        """
        now = timezone.localtime()
        prefix = f"REC-{now.strftime('%Y%m')}-"
        last_payment = cls.objects.filter(receipt_number__startswith=prefix).order_by('-receipt_number').first()
        if last_payment:
            try:
                last_seq = int(last_payment.receipt_number.split('-')[-1])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        return f"{prefix}{new_seq:04d}"

    @property
    def total_principal_applied(self) -> Decimal:
        return self.allocations.aggregate(
            total=models.Sum('principal_applied')
        )['total'] or Decimal('0.00')

    @property
    def total_interest_applied(self) -> Decimal:
        return self.allocations.aggregate(
            total=models.Sum('interest_applied')
        )['total'] or Decimal('0.00')

    @property
    def is_reversed(self) -> bool:
        return self.status == self.Status.REVERSED


class PaymentAllocation(BaseModel):
    """
    Tracks precise distribution of a Payment into specific Installments,
    detailing how much was credited to principal vs interest.
    """
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name="Pago"
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.PROTECT,
        related_name='allocations',
        verbose_name="Cuota"
    )
    principal_applied = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Capital amortizado"
    )
    interest_applied = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Interés pagado"
    )
    total_applied = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Total aplicado a la cuota"
    )

    class Meta:
        verbose_name = "Imputación de Pago"
        verbose_name_plural = "Imputaciones de Pago"
        ordering = ['installment__installment_number']

    def __str__(self):
        return f"Imputación {self.payment.receipt_number} -> Cuota #{self.installment.installment_number}: ${self.total_applied:,.0f}"

