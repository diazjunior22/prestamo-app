from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from apps.notifications.models import NotificationLog
from apps.notifications.services.email_service import EmailNotificationService
from apps.loans.models import Installment

@login_required
def notification_list_view(request):
    """
    Central hub for email notifications, Gmail SMTP status,
    delivery logs and diagnostic tools.
    """
    smtp_status = EmailNotificationService.get_smtp_status()

    # Logs queryset with search & filtering
    logs_qs = NotificationLog.objects.all().order_by('-created_at')

    search = request.GET.get('search', '').strip()
    if search:
        logs_qs = logs_qs.filter(
            Q(recipient_email__icontains=search) |
            Q(recipient_name__icontains=search) |
            Q(subject__icontains=search) |
            Q(loan_reference__icontains=search) |
            Q(payment_reference__icontains=search)
        )

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        logs_qs = logs_qs.filter(status=status_filter)

    type_filter = request.GET.get('type', '').strip()
    if type_filter:
        logs_qs = logs_qs.filter(notification_type=type_filter)

    # Metrics
    total_logs = NotificationLog.objects.count()
    sent_logs = NotificationLog.objects.filter(status=NotificationLog.Status.SENT).count()
    failed_logs = NotificationLog.objects.filter(status=NotificationLog.Status.FAILED).count()

    paginator = Paginator(logs_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'active_nav': 'notifications',
        'smtp_status': smtp_status,
        'logs': page_obj,
        'page_obj': page_obj,
        'total_logs': total_logs,
        'sent_logs': sent_logs,
        'failed_logs': failed_logs,
        'search': search,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'type_choices': NotificationLog.NotificationType.choices,
        'status_choices': NotificationLog.Status.choices,
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
def notification_send_test_view(request):
    """Handles sending an immediate test email."""
    if request.method == 'POST':
        test_email = request.POST.get('test_email', '').strip()
        if not test_email:
            messages.error(request, "Ingresa una dirección de correo para enviar la prueba.")
            return redirect('notifications:list')

        success, msg = EmailNotificationService.send_test_email(test_email)
        if success:
            messages.success(request, f"¡Éxito! {msg}")
        else:
            messages.error(request, f"Fallo al enviar correo: {msg}")

    return redirect('notifications:list')


@login_required
def notification_trigger_reminders_view(request):
    """Dispatches reminders for all installments due today."""
    if request.method == 'POST':
        today = timezone.localdate()
        due_installments = Installment.objects.filter(
            due_date=today,
            status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL]
        ).select_related('customer', 'loan')

        sent = 0
        skipped = 0
        for inst in due_installments:
            if inst.customer.email:
                success, _ = EmailNotificationService.send_installment_reminder_email(inst)
                if success:
                    sent += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        messages.success(
            request,
            f"Proceso finalizado: {sent} recordatorios enviados exitosamente. {skipped} cuotas sin correo o fallidas."
        )

    return redirect('notifications:list')


@login_required
def notification_trigger_digest_view(request):
    """Dispatches the daily operational digest report to admin email."""
    if request.method == 'POST':
        admin_email = request.POST.get('admin_email', '').strip() or None
        success, msg = EmailNotificationService.send_daily_digest_email(admin_email)
        if success:
            messages.success(request, f"Reporte matutino despachado: {msg}")
        else:
            messages.error(request, f"No se pudo enviar el reporte: {msg}")

    return redirect('notifications:list')


@login_required
def notification_detail_modal_view(request, pk):
    """Returns HTML snippet of the rendered email body for preview."""
    log = get_object_or_404(NotificationLog, pk=pk)
    return render(request, 'notifications/partials/log_preview.html', {'log': log})
