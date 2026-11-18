from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.loans.services.loan_creator import LoanCreator
from apps.payments.models import Payment
from apps.payments.services.payment_allocator import allocate_payment
from apps.cashflow.models import CashAccount, CashMovement
from apps.notifications.models import NotificationLog
from apps.notifications.services.email_service import EmailNotificationService

User = get_user_model()

class NotificationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            email='admin_notif@test.local',
            username='admin_notif',
            password='Password123!',
            first_name='Admin',
            last_name='Notif'
        )
        self.client.login(email='admin_notif@test.local', password='Password123!')

        CashAccount.ensure_default_accounts()

        # Customer with email
        self.customer = Customer.objects.create(
            first_name='Carlos',
            last_name='Mendoza',
            document_type='CC',
            document_number='1098765432',
            phone='3001234567',
            email='carlos.mendoza@test.local',
            address='Calle 45 # 10-20',
            city='Bogotá'
        )

        # Create a loan for testing notifications
        today = timezone.localdate()
        self.loan = LoanCreator.create_loan(
            customer=self.customer,
            principal=Decimal('1000000.00'),
            interest_rate=Decimal('5.00'),
            interest_rate_period=Loan.RatePeriod.MONTHLY,
            interest_type=Loan.InterestType.FLAT,
            payment_frequency=Loan.PaymentFrequency.MONTHLY,
            total_installments=4,
            disbursement_date=today,
            first_payment_date=today + timezone.timedelta(days=30),
            notes='Préstamo test notificaciones',
            user=self.user
        )

        # Clear outbox generated during setup (from automatic loan creation email)
        mail.outbox = []

    def test_smtp_status(self):
        """Service accurately reports SMTP status dict."""
        status = EmailNotificationService.get_smtp_status()
        self.assertIn('is_smtp', status)
        self.assertIn('host', status)
        self.assertIn('port', status)
        self.assertEqual(status['host'], 'smtp.gmail.com')
        self.assertEqual(status['port'], 587)

    def test_send_test_email(self):
        """Test email sends via backend and logs in database."""
        success, msg = EmailNotificationService.send_test_email('test_recipient@test.local')
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Prueba de Conexión de Correo Gmail", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['test_recipient@test.local'])

        log = NotificationLog.objects.filter(recipient_email='test_recipient@test.local').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.notification_type, NotificationLog.NotificationType.TEST)
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_send_loan_created_email(self):
        """Loan confirmation email renders details and sends to customer email."""
        success, msg = EmailNotificationService.send_loan_created_email(self.loan)
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.loan.loan_code, mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.customer.email])

        log = NotificationLog.objects.filter(loan_reference=self.loan.loan_code).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.notification_type, NotificationLog.NotificationType.LOAN_CREATED)

    def test_send_payment_receipt_email(self):
        """Payment receipt sends email with PDF attachment."""
        payment = allocate_payment(
            loan=self.loan,
            amount=Decimal('300000.00'),
            user=self.user
        )

        success, msg = EmailNotificationService.send_payment_receipt_email(payment)
        self.assertTrue(success)
        # Check outbox
        latest_mail = mail.outbox[-1]
        self.assertIn(payment.receipt_number, latest_mail.subject)
        self.assertEqual(latest_mail.to, [self.customer.email])
        # Verify PDF attachment
        self.assertTrue(any(att[0].endswith('.pdf') for att in latest_mail.attachments))

        log = NotificationLog.objects.filter(payment_reference=payment.receipt_number).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.notification_type, NotificationLog.NotificationType.PAYMENT_RECEIPT)

    def test_send_installment_reminder_email(self):
        """Installment reminder notifies customer about due or overdue quota."""
        inst = self.loan.installments.first()
        success, msg = EmailNotificationService.send_installment_reminder_email(inst)
        self.assertTrue(success)

        latest_mail = mail.outbox[-1]
        self.assertIn(f"Cuota #{inst.installment_number}", latest_mail.subject)

    def test_send_daily_digest_email(self):
        """Daily operations digest generates summary for admin."""
        success, msg = EmailNotificationService.send_daily_digest_email('admin_digest@test.local')
        self.assertTrue(success)
        latest_mail = mail.outbox[-1]
        self.assertIn("Reporte Matutino de Cobranza", latest_mail.subject)
        self.assertEqual(latest_mail.to, ['admin_digest@test.local'])

    def test_notifications_views_flow(self):
        """Views for notification center, sending test, triggers and modal preview."""
        # 1. Notification list
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notificaciones Gratuitas por Gmail')
        self.assertContains(response, 'smtp.gmail.com')

        # 2. Trigger test email POST
        response = self.client.post(reverse('notifications:send_test'), {'test_email': 'live_test@test.local'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(NotificationLog.objects.filter(recipient_email='live_test@test.local').exists())

        # 3. Trigger reminders POST
        response = self.client.post(reverse('notifications:trigger_reminders'))
        self.assertEqual(response.status_code, 302)

        # 4. Trigger digest POST
        response = self.client.post(reverse('notifications:trigger_digest'), {'admin_email': 'admin_run@test.local'})
        self.assertEqual(response.status_code, 302)

        # 5. Loan send email action
        response = self.client.post(reverse('loans:send_email', args=[self.loan.pk]))
        self.assertEqual(response.status_code, 302)

        # 6. Payment send email action
        payment = allocate_payment(loan=self.loan, amount=Decimal('100000.00'), user=self.user)
        response = self.client.post(reverse('payments:send_email', args=[payment.pk]))
        self.assertEqual(response.status_code, 302)
