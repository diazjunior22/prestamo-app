from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.notifications.services.email_service import EmailNotificationService

class Command(BaseCommand):
    help = 'Dispara los recordatorios automáticos (1 día antes y el mismo día de pago) y el reporte matutino al administrador.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timezone.timedelta(days=1)
        self.stdout.write(self.style.NOTICE(f"Iniciando ciclo automático de notificaciones para {today}..."))

        # 1. Dispatch automatic customer reminders (Hoy y Mañana)
        results = EmailNotificationService.dispatch_automatic_reminders(check_duplicates=True)

        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios preventivos (Vencen Mañana {tomorrow.strftime('%d/%m')}): {results['eve_sent']} enviados."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Alertas de cobro (Vencen Hoy {today.strftime('%d/%m')}): {results['today_sent']} enviadas."
        ))
        if results['skipped_duplicate'] > 0:
            self.stdout.write(self.style.WARNING(
                f"Omitidos por duplicado (ya enviados hoy): {results['skipped_duplicate']} cuotas."
            ))
        if results['skipped_no_email'] > 0:
            self.stdout.write(self.style.WARNING(
                f"Omitidos (clientes sin correo): {results['skipped_no_email']} cuotas."
            ))

        # 2. Dispatch Daily Digest to Administrator
        success, digest_msg = EmailNotificationService.send_daily_digest_email()
        if success:
            self.stdout.write(self.style.SUCCESS(f"Reporte matutino al administrador: {digest_msg}"))
        else:
            self.stdout.write(self.style.ERROR(f"Error en reporte matutino: {digest_msg}"))
