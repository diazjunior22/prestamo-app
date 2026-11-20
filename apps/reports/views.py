from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.payments.models import Payment
from apps.cashflow.models import CashMovement
from apps.reports.services.backup_service import BackupService

@login_required
def report_list_view(request):
    """
    Renders reports dashboard with database metrics and disaster recovery/backup controls.
    """
    total_customers = Customer.objects.count()
    total_loans = Loan.objects.count()
    active_loans = Loan.objects.filter(status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE]).count()
    total_payments = Payment.objects.count()
    total_movements = CashMovement.objects.count()

    context = {
        'active_nav': 'reports',
        'total_customers': total_customers,
        'total_loans': total_loans,
        'active_loans': active_loans,
        'total_payments': total_payments,
        'total_movements': total_movements,
    }
    return render(request, 'reports/report_list.html', context)


@login_required
def backup_export_view(request):
    """
    Exports a full database backup in JSON format for offsite disaster recovery.
    """
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "Solo administradores pueden descargar copias de seguridad.")
        return redirect('reports:list')

    try:
        json_backup = BackupService.generate_full_backup_json()
        timestamp = timezone.localtime().strftime('%Y-%m-%d_%H%M%S')
        filename = f"backup_prestamos_{timestamp}.json"

        response = HttpResponse(json_backup, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Error al generar la copia de seguridad: {str(e)}")
        return redirect('reports:list')


@login_required
def backup_restore_view(request):
    """
    Restores the database state from an uploaded JSON backup file.
    """
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "Solo administradores pueden restaurar copias de seguridad.")
        return redirect('reports:list')

    if request.method == 'POST':
        backup_file = request.FILES.get('backup_file')
        if not backup_file:
            messages.error(request, "Por favor selecciona un archivo de copia de seguridad (.json).")
            return redirect('reports:list')

        if not backup_file.name.endswith('.json'):
            messages.error(request, "El archivo debe tener extensión .json.")
            return redirect('reports:list')

        try:
            content = backup_file.read()
            count = BackupService.restore_backup_json(content)
            messages.success(request, f"Copia de seguridad restaurada exitosamente. Se sincronizaron {count} registros.")
        except Exception as e:
            messages.error(request, f"Error al restaurar la copia de seguridad: {str(e)}")

    return redirect('reports:list')
