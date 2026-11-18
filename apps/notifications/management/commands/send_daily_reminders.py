from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.loans.models import Installment
from apps.notifications.services.email_service import EmailNotificationService

class Command(BaseCommand):
    help = 'Dispara los recordatorios por correo de las cuotas que vencen hoy y el reporte matutino al administrador.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        self.stdout.write(self.style.NOTICE(f"Iniciando procesamiento de notificaciones para {today}..."))

        # 1. Send reminders for installments due today
        installments_today = Installment.objects.filter(
            due_date=today,
            status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL]
        ).select_related('customer', 'loan')

        sent_count = 0
        skipped_count = 0

        for inst in installments_today:
            if inst.customer.email:
                success, msg = EmailNotificationService.send_installment_reminder_email(inst)
                if success:
                    sent_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"Fallo al enviar a {inst.customer.full_name}: {msg}"))
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios de cuotas: {sent_count} enviados, {skipped_count} omitidos (sin correo)."
        ))

        # 2. Send daily digest to admin
        success, digest_msg = EmailNotificationService.send_daily_digest_email()
        if success:
            self.stdout.write(self.style.SUCCESS(f"Reporte matutino: {digest_msg}"))
        else:
            self.stdout.write(self.style.ERROR(f"Error en reporte matutino: {digest_msg}"))

