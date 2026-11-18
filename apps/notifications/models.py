import uuid
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel

class NotificationLog(BaseModel):
    """
    Audit log of all notifications dispatched by the system (via Gmail SMTP, etc.).
    Keeps a verifiable record of when emails were sent, to whom, their status,
    and any error trace if delivery failed.
    """
    class NotificationType(models.TextChoices):
        LOAN_CREATED = 'LOAN_CREATED', 'Desembolso / Nuevo Préstamo'
        PAYMENT_RECEIPT = 'PAYMENT_RECEIPT', 'Comprobante de Pago'
        DUE_REMINDER = 'DUE_REMINDER', 'Recordatorio Preventivo (Vence Mañana)'
        DUE_TODAY = 'DUE_TODAY', 'Alerta de Pago (Vence Hoy)'
        OVERDUE_ALERT = 'OVERDUE_ALERT', 'Alerta de Cuota Vencida (En Mora)'
        DAILY_DIGEST = 'DAILY_DIGEST', 'Resumen Matutino de Cobranza'
        TEST = 'TEST', 'Prueba de Conexión Gmail'

    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', 'Correo Electrónico (Gmail)'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        SMS = 'SMS', 'Mensaje de Texto'

    class Status(models.TextChoices):
        SENT = 'SENT', 'Enviado con Éxito'
        FAILED = 'FAILED', 'Fallido'
        PENDING = 'PENDING', 'Pendiente'

    recipient_email = models.EmailField(
        verbose_name="Correo destinatario"
    )
    recipient_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Nombre destinatario"
    )
    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
        default=NotificationType.TEST,
        verbose_name="Tipo de notificación"
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.EMAIL,
        verbose_name="Canal de envío"
    )
    subject = models.CharField(
        max_length=255,
        verbose_name="Asunto"
    )
    body_html = models.TextField(
        blank=True,
        verbose_name="Contenido HTML"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado de entrega"
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name="Detalle del error"
    )

    # Contextual references
    customer_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Cliente asociado"
    )
    loan_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Código de préstamo"
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="N° de recibo"
    )

    class Meta:
        verbose_name = "Registro de Notificación"
        verbose_name_plural = "Historial de Notificaciones"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notification_type_display()}] a {self.recipient_email} ({self.get_status_display()})"

