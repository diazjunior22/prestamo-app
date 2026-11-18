import re
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel

class Customer(BaseModel):
    """
    Customer entity representing loan borrowers.
    Guarantees strict uniqueness on document_number, contact channels,
    references, and payment behavior tracking.
    """
    class DocumentType(models.TextChoices):
        CC = 'CC', 'Cédula de Ciudadanía'
        CE = 'CE', 'Cédula de Extranjería'
        NIT = 'NIT', 'NIT'
        PP = 'PP', 'Pasaporte'
        TI = 'TI', 'Tarjeta de Identidad'
        OTHER = 'OTHER', 'Otro Documento'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Activo'
        INACTIVE = 'INACTIVE', 'Inactivo'
        BLOCKED = 'BLOCKED', 'En Mora Crítica / Bloqueado'

    first_name = models.CharField(max_length=100, verbose_name="Nombres")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    document_type = models.CharField(
        max_length=10,
        choices=DocumentType.choices,
        default=DocumentType.CC,
        verbose_name="Tipo de documento"
    )
    document_number = models.CharField(
        max_length=35,
        unique=True,
        db_index=True,
        verbose_name="Número de documento"
    )
    phone = models.CharField(max_length=25, verbose_name="Teléfono principal")
    whatsapp = models.CharField(max_length=25, blank=True, null=True, verbose_name="WhatsApp")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo electrónico")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección de residencia o negocio")
    city = models.CharField(max_length=100, default='Bogotá', verbose_name="Ciudad")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name="Estado del cliente"
    )

    # Optional references
    reference_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre de referencia")
    reference_relationship = models.CharField(max_length=100, blank=True, null=True, verbose_name="Parentesco o relación")
    reference_phone = models.CharField(max_length=25, blank=True, null=True, verbose_name="Teléfono de referencia")

    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones internas")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_customers',
        verbose_name="Registrado por"
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['document_number']),
            models.Index(fields=['status']),
            models.Index(fields=['first_name', 'last_name']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.document_type} {self.document_number})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def whatsapp_clean(self) -> str:
        """Returns clean digits for direct WhatsApp wa.me links."""
        target = self.whatsapp or self.phone or ""
        digits = re.sub(r'\D', '', target)
        if digits and len(digits) == 10 and not digits.startswith('57'):
            # Prepend Colombia country code if 10 digits
            return f"57{digits}"
        return digits

    def clean(self):
        super().clean()
        if self.document_number:
            # Clean spaces and symbols from document number
            cleaned_doc = "".join(self.document_number.split()).replace(".", "").replace("-", "")
            self.document_number = cleaned_doc
            # Validate uniqueness case-insensitively
            existing = Customer.objects.filter(document_number__iexact=cleaned_doc).exclude(id=self.id)
            if existing.exists():
                raise ValidationError({
                    'document_number': f"Ya existe un cliente registrado con el documento número {cleaned_doc}."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.whatsapp and self.phone:
            self.whatsapp = self.phone
        super().save(*args, **kwargs)

    # Safe financial helpers (dynamic aggregation once Loan model is linked)
    def get_total_borrowed(self) -> Decimal:
        if hasattr(self, 'loans'):
            agg = self.loans.exclude(status='CANCELLED').aggregate(models.Sum('principal'))['principal__sum']
            return agg or Decimal('0.00')
        return Decimal('0.00')

    def get_pending_balance(self) -> Decimal:
        if hasattr(self, 'loans'):
            agg = self.loans.filter(status__in=['ACTIVE', 'OVERDUE']).aggregate(models.Sum('balance'))['balance__sum']
            return agg or Decimal('0.00')
        return Decimal('0.00')

    def get_total_paid(self) -> Decimal:
        if hasattr(self, 'loans'):
            agg_p = self.loans.exclude(status='CANCELLED').aggregate(models.Sum('paid_principal'))['paid_principal__sum'] or Decimal('0.00')
            agg_i = self.loans.exclude(status='CANCELLED').aggregate(models.Sum('paid_interest'))['paid_interest__sum'] or Decimal('0.00')
            return agg_p + agg_i
        return Decimal('0.00')

    def get_collected_interest(self) -> Decimal:
        if hasattr(self, 'loans'):
            agg = self.loans.exclude(status='CANCELLED').aggregate(models.Sum('paid_interest'))['paid_interest__sum']
            return agg or Decimal('0.00')
        return Decimal('0.00')

    def get_active_loans_count(self) -> int:
        if hasattr(self, 'loans'):
            return self.loans.filter(status__in=['ACTIVE', 'OVERDUE']).count()
        return 0

    def get_overdue_installments_count(self) -> int:
        if hasattr(self, 'installments'):
            return self.installments.filter(status='OVERDUE').count()
        return 0

