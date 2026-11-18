import logging
from decimal import Decimal
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from apps.notifications.models import NotificationLog

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """
    Service responsible for rendering and sending free transactional emails
    via Google's Gmail SMTP server (smtp.gmail.com:587) or development console.
    Tracks every dispatch in the database via NotificationLog.
    """

    @classmethod
    def get_smtp_status(cls) -> dict:
        """
        Returns the current configuration status of the email subsystem.
        """
        host_user = getattr(settings, 'EMAIL_HOST_USER', '')
        has_password = bool(getattr(settings, 'EMAIL_HOST_PASSWORD', ''))
        backend = getattr(settings, 'EMAIL_BACKEND', '')
        is_smtp = 'smtp' in backend.lower() and bool(host_user and has_password)

        return {
            'is_smtp': is_smtp,
            'host_user': host_user,
            'has_password': has_password,
            'backend': backend,
            'host': getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com'),
            'port': getattr(settings, 'EMAIL_PORT', 587),
            'default_from': getattr(settings, 'DEFAULT_FROM_EMAIL', ''),
            'admin_email': getattr(settings, 'ADMIN_EMAIL', 'admin@loanmanager.local')
        }

    @classmethod
    def _send_email_message(
        cls,
        subject: str,
        template_name: str,
        context: dict,
        to_email: str,
        recipient_name: str = '',
        notification_type: str = NotificationLog.NotificationType.TEST,
        attachments: list = None,
        customer_ref: str = None,
        loan_ref: str = None,
        payment_ref: str = None,
    ) -> tuple[bool, str]:
        """
        Generic helper to render HTML template, build multipart email with attachments,
        send message, and persist delivery status in NotificationLog.
        """
        if not to_email or not to_email.strip():
            return False, "No se proporcionó una dirección de correo válida."

        to_email = to_email.strip()
        system_name = getattr(settings, 'SYSTEM_NAME', 'LoanManager')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', f"{system_name} <notificaciones@loanmanager.local>")

        context.setdefault('system_name', system_name)
        context.setdefault('from_email', from_email)
        context.setdefault('to_email', to_email)
        context.setdefault('sent_at', timezone.now())

        try:
            html_content = render_to_string(template_name, context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=f"[{system_name}] {subject}",
                body=text_content,
                from_email=from_email,
                to=[to_email]
            )
            email.attach_alternative(html_content, "text/html")

            # Attach files if provided: list of tuples (filename, content, mimetype)
            if attachments:
                for attachment in attachments:
                    if len(attachment) == 3:
                        email.attach(attachment[0], attachment[1], attachment[2])

            email.send(fail_silently=False)

            # Record success in log
            NotificationLog.objects.create(
                recipient_email=to_email,
                recipient_name=recipient_name,
                notification_type=notification_type,
                channel=NotificationLog.Channel.EMAIL,
                subject=subject,
                body_html=html_content,
                status=NotificationLog.Status.SENT,
                customer_reference=customer_ref,
                loan_reference=loan_ref,
                payment_reference=payment_ref,
            )

            logger.info(f"Email successfully dispatched to {to_email} ({notification_type})")
            return True, f"Correo enviado exitosamente a {to_email}."

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send email to {to_email}: {error_msg}")

            # Record failure in log
            NotificationLog.objects.create(
                recipient_email=to_email,
                recipient_name=recipient_name,
                notification_type=notification_type,
                channel=NotificationLog.Channel.EMAIL,
                subject=subject,
                body_html="",
                status=NotificationLog.Status.FAILED,
                error_message=error_msg,
                customer_reference=customer_ref,
                loan_reference=loan_ref,
                payment_reference=payment_ref,
            )

            return False, f"Error al enviar correo: {error_msg}"

    @classmethod
    def send_test_email(cls, to_email: str) -> tuple[bool, str]:
        """
        Sends an immediate test email to verify Gmail SMTP connection.
        """
        subject = "Prueba de Conexión de Correo Gmail"
        context = {
            'to_email': to_email,
        }
        return cls._send_email_message(
            subject=subject,
            template_name='emails/test_email.html',
            context=context,
            to_email=to_email,
            recipient_name="Administrador / Tester",
            notification_type=NotificationLog.NotificationType.TEST
        )

    @classmethod
    def send_loan_created_email(cls, loan, recipient_email: str = None) -> tuple[bool, str]:
        """
        Sends loan confirmation and payment plan summary to customer.
        """
        customer = loan.customer
        to_email = recipient_email or getattr(customer, 'email', None)

        if not to_email:
            to_email = getattr(settings, 'ADMIN_EMAIL', '')

        if not to_email:
            return False, "El cliente no tiene correo electrónico registrado."

        first_inst = loan.installments.order_by('installment_number').first()

        context = {
            'loan': loan,
            'customer': customer,
            'first_installment': first_inst,
        }
        subject = f"Confirmación de Préstamo {loan.loan_code} — {customer.full_name}"

        return cls._send_email_message(
            subject=subject,
            template_name='emails/loan_created.html',
            context=context,
            to_email=to_email,
            recipient_name=customer.full_name,
            notification_type=NotificationLog.NotificationType.LOAN_CREATED,
            customer_ref=customer.full_name,
            loan_ref=loan.loan_code
        )

    @classmethod
    def send_payment_receipt_email(cls, payment, recipient_email: str = None) -> tuple[bool, str]:
        """
        Sends payment receipt with PDF attachment to customer.
        """
        customer = payment.customer
        loan = payment.loan
        to_email = recipient_email or getattr(customer, 'email', None)

        if not to_email:
            to_email = getattr(settings, 'ADMIN_EMAIL', '')

        if not to_email:
            return False, "El cliente no tiene correo electrónico registrado."

        next_inst = loan.installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).order_by('installment_number').first()

        context = {
            'payment': payment,
            'customer': customer,
            'loan': loan,
            'next_installment': next_inst,
        }
        subject = f"Comprobante de Pago Recibo {payment.receipt_number}"

        attachments = []
        try:
            from apps.payments.services.receipt_generator import build_receipt_pdf_bytes
            pdf_bytes = build_receipt_pdf_bytes(payment)
            attachments.append((f"Recibo_{payment.receipt_number}.pdf", pdf_bytes, 'application/pdf'))
        except Exception as e:
            logger.warning(f"Could not attach PDF receipt to email: {e}")

        return cls._send_email_message(
            subject=subject,
            template_name='emails/payment_receipt.html',
            context=context,
            to_email=to_email,
            recipient_name=customer.full_name,
            notification_type=NotificationLog.NotificationType.PAYMENT_RECEIPT,
            attachments=attachments,
            customer_ref=customer.full_name,
            loan_ref=loan.loan_code,
            payment_ref=payment.receipt_number
        )

    @classmethod
    def send_installment_reminder_email(
        cls,
        installment,
        timing: str = 'AUTO',
        recipient_email: str = None
    ) -> tuple[bool, str]:
        """
        Sends installment reminder/alert.
        Supports:
        - 'EVE': 1 día antes del vencimiento (Recordatorio preventivo: Mañana vence tu cuota).
        - 'TODAY': Mismo día del vencimiento (Alerta de cobro: Hoy vence tu cuota).
        - 'OVERDUE': En mora (Alerta de cuota vencida).
        - 'AUTO': Automatically resolves based on comparison with today's date.
        """
        customer = installment.customer
        loan = installment.loan
        to_email = recipient_email or getattr(customer, 'email', None)

        if not to_email:
            return False, f"El cliente {customer.full_name} no tiene correo registrado."

        today = timezone.localdate()
        diff_days = (installment.due_date - today).days

        if timing == 'AUTO':
            if diff_days == 1:
                timing = 'EVE'
            elif diff_days == 0:
                timing = 'TODAY'
            elif diff_days < 0:
                timing = 'OVERDUE'
            else:
                timing = 'UPCOMING'

        is_overdue = timing == 'OVERDUE' or diff_days < 0

        context = {
            'installment': installment,
            'loan': loan,
            'customer': customer,
            'timing': timing,
            'is_overdue': is_overdue,
        }

        if timing == 'EVE':
            subject = f"Recordatorio: Mañana vence tu cuota #{installment.installment_number} — Préstamo {loan.loan_code}"
            notif_type = NotificationLog.NotificationType.DUE_REMINDER
        elif timing == 'TODAY':
            subject = f"Alerta de Cobro: Hoy vence tu cuota #{installment.installment_number} — Préstamo {loan.loan_code}"
            notif_type = NotificationLog.NotificationType.DUE_TODAY
        elif is_overdue:
            subject = f"Aviso de Mora: Cuota #{installment.installment_number} vencida — Préstamo {loan.loan_code}"
            notif_type = NotificationLog.NotificationType.OVERDUE_ALERT
        else:
            subject = f"Recordatorio de Vencimiento Cuota #{installment.installment_number} — {loan.loan_code}"
            notif_type = NotificationLog.NotificationType.DUE_REMINDER

        return cls._send_email_message(
            subject=subject,
            template_name='emails/due_reminder.html',
            context=context,
            to_email=to_email,
            recipient_name=customer.full_name,
            notification_type=notif_type,
            customer_ref=customer.full_name,
            loan_ref=loan.loan_code
        )

    @classmethod
    def dispatch_automatic_reminders(cls, check_duplicates: bool = True) -> dict:
        """
        Runs the daily automated reminder cycle:
        1. Finds all installments due TOMORROW (1 día antes) and sends 'Recordatorio Preventivo' (EVE).
        2. Finds all installments due TODAY (mismo día) and sends 'Alerta de Pago' (TODAY).
        Avoids spamming duplicates if an alert was already successfully dispatched today.
        """
        today = timezone.localdate()
        tomorrow = today + timezone.timedelta(days=1)

        from apps.loans.models import Installment

        results = {
            'eve_sent': 0,
            'today_sent': 0,
            'skipped_no_email': 0,
            'skipped_duplicate': 0,
            'failed': 0,
        }

        # 1. Cuotas que vencen MAÑANA (un día antes)
        tomorrow_installments = Installment.objects.filter(
            due_date=tomorrow,
            status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL]
        ).select_related('customer', 'loan')

        for inst in tomorrow_installments:
            if not inst.customer.email:
                results['skipped_no_email'] += 1
                continue

            if check_duplicates:
                already_sent = NotificationLog.objects.filter(
                    recipient_email=inst.customer.email,
                    loan_reference=inst.loan.loan_code,
                    notification_type=NotificationLog.NotificationType.DUE_REMINDER,
                    status=NotificationLog.Status.SENT,
                    created_at__date=today
                ).exists()
                if already_sent:
                    results['skipped_duplicate'] += 1
                    continue

            success, _ = cls.send_installment_reminder_email(inst, timing='EVE')
            if success:
                results['eve_sent'] += 1
            else:
                results['failed'] += 1

        # 2. Cuotas que vencen HOY (mismo día)
        today_installments = Installment.objects.filter(
            due_date=today,
            status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL]
        ).select_related('customer', 'loan')

        for inst in today_installments:
            if not inst.customer.email:
                results['skipped_no_email'] += 1
                continue

            if check_duplicates:
                already_sent = NotificationLog.objects.filter(
                    recipient_email=inst.customer.email,
                    loan_reference=inst.loan.loan_code,
                    notification_type=NotificationLog.NotificationType.DUE_TODAY,
                    status=NotificationLog.Status.SENT,
                    created_at__date=today
                ).exists()
                if already_sent:
                    results['skipped_duplicate'] += 1
                    continue

            success, _ = cls.send_installment_reminder_email(inst, timing='TODAY')
            if success:
                results['today_sent'] += 1
            else:
                results['failed'] += 1

        return results

    @classmethod
    def send_daily_digest_email(cls, admin_email: str = None) -> tuple[bool, str]:
        """
        Generates and sends the daily operations report to the administrator:
        - Cuotas que vencen HOY.
        - Cuotas que vencen MAÑANA (un día antes).
        - Cuotas en mora.
        - Saldos disponibles en cada bolsillo (Caja, Nequi, Nu, Bancos).
        """
        to_email = admin_email or getattr(settings, 'ADMIN_EMAIL', 'admin@loanmanager.local')
        if not to_email:
            return False, "No se ha configurado un correo de administrador."

        today = timezone.localdate()
        tomorrow = today + timezone.timedelta(days=1)

        from apps.loans.models import Loan, Installment
        from apps.cashflow.models import CashAccount, CashMovement

        # Installments due TODAY
        today_installments = Installment.objects.filter(
            due_date=today,
            status__in=['PENDING', 'PARTIAL']
        ).select_related('customer', 'loan').order_by('customer__last_name')

        today_due_count = today_installments.count()
        today_due_amount = sum((i.balance for i in today_installments), Decimal('0.00'))

        # Installments due TOMORROW (1 día antes)
        tomorrow_installments = Installment.objects.filter(
            due_date=tomorrow,
            status__in=['PENDING', 'PARTIAL']
        ).select_related('customer', 'loan').order_by('customer__last_name')

        tomorrow_due_count = tomorrow_installments.count()
        tomorrow_due_amount = sum((i.balance for i in tomorrow_installments), Decimal('0.00'))

        # Overdue installments
        overdue_installments = Installment.objects.filter(
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        )
        overdue_count = overdue_installments.count()
        overdue_amount = sum((i.balance for i in overdue_installments), Decimal('0.00'))

        # Active loans
        active_loans = Loan.objects.filter(status=Loan.Status.ACTIVE)
        active_loans_count = active_loans.count()
        total_outstanding_balance = sum((l.balance for l in active_loans), Decimal('0.00'))

        # Account pocket balances
        accounts_data = []
        for acc in CashAccount.objects.filter(is_active=True).order_by('name'):
            accounts_data.append({
                'name': acc.name,
                'balance': acc.get_current_balance()
            })

        total_cash = CashMovement.get_current_balance()

        context = {
            'report_date': today,
            'today_due_count': today_due_count,
            'today_due_amount': today_due_amount,
            'tomorrow_due_count': tomorrow_due_count,
            'tomorrow_due_amount': tomorrow_due_amount,
            'overdue_count': overdue_count,
            'overdue_amount': overdue_amount,
            'active_loans_count': active_loans_count,
            'total_outstanding_balance': total_outstanding_balance,
            'accounts': accounts_data,
            'total_cash': total_cash,
            'today_installments': today_installments[:25],
            'tomorrow_installments': tomorrow_installments[:25],
            'site_url': 'http://localhost:8000',
        }

        subject = f"Reporte de Cobranza (Hoy: {today_due_count} cuotas | Mañana: {tomorrow_due_count} cuotas) — {today.strftime('%d/%m/%Y')}"

        return cls._send_email_message(
            subject=subject,
            template_name='emails/daily_digest.html',
            context=context,
            to_email=to_email,
            recipient_name="Administrador",
            notification_type=NotificationLog.NotificationType.DAILY_DIGEST
        )
