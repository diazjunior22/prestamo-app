import datetime
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from apps.customers.models import Customer
from apps.cashflow.models import CashMovement
from .models import Loan, Installment
from .forms import LoanForm
from .services.loan_calculator import LoanCalculator
from .services.loan_creator import LoanCreator

@login_required
def loan_list_view(request):
    """
    List of loans with search, status filtering, and financial metrics.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    customer_filter = request.GET.get('customer', '').strip()

    loans_qs = Loan.objects.select_related('customer').all().order_by('-disbursement_date', '-created_at')

    if query:
        loans_qs = loans_qs.filter(
            Q(loan_code__icontains=query) |
            Q(customer__first_name__icontains=query) |
            Q(customer__last_name__icontains=query) |
            Q(customer__document_number__icontains=query)
        )

    if status_filter:
        loans_qs = loans_qs.filter(status=status_filter)

    if customer_filter:
        loans_qs = loans_qs.filter(customer_id=customer_filter)

    # Aggregations
    total_principal = Loan.objects.exclude(status='CANCELLED').aggregate(Sum('principal'))['principal__sum'] or Decimal('0.00')
    total_balance = Loan.objects.filter(status__in=['ACTIVE', 'OVERDUE']).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    active_count = Loan.objects.filter(status__in=['ACTIVE', 'OVERDUE']).count()

    paginator = Paginator(loans_qs, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Cartera de Préstamos',
        'active_nav': 'loans',
        'page_obj': page_obj,
        'loans': page_obj.object_list,
        'query': query,
        'status_filter': status_filter,
        'total_principal': total_principal,
        'total_balance': total_balance,
        'active_count': active_count,
    }
    return render(request, 'loans/loan_list.html', context)


@login_required
def loan_create_view(request):
    """
    Form view to originate a loan.
    Integrates live HTMX simulation before confirmation and executes
    an atomic transaction upon submission.
    """
    customer_id = request.GET.get('customer_id')

    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            try:
                loan = LoanCreator.create_loan(
                    customer=form.cleaned_data['customer'],
                    principal=form.cleaned_data['principal'],
                    interest_rate=form.cleaned_data['interest_rate'],
                    interest_rate_period=form.cleaned_data.get('interest_rate_period', 'MONTHLY'),
                    interest_type=form.cleaned_data['interest_type'],
                    payment_frequency=form.cleaned_data['payment_frequency'],
                    total_installments=form.cleaned_data['total_installments'],
                    disbursement_date=form.cleaned_data['disbursement_date'],
                    first_payment_date=form.cleaned_data['first_payment_date'],
                    notes=form.cleaned_data.get('notes', ''),
                    user=request.user
                )
                messages.success(request, f"Préstamo {loan.loan_code} creado y desembolsado exitosamente con {loan.total_installments} cuotas.")
                return redirect('loans:detail', pk=loan.pk)
            except Exception as e:
                messages.error(request, f"Error al generar el préstamo: {str(e)}")
        else:
            messages.error(request, "Por favor corrige los errores señalados en el formulario.")
    else:
        form = LoanForm(initial_customer_id=customer_id)

    return render(request, 'loans/loan_form.html', {
        'form': form,
        'page_title': 'Registrar Nuevo Préstamo',
        'active_nav': 'loans',
    })


@login_required
def loan_simulate_view(request):
    """
    HTMX endpoint calculating and returning the real-time amortization schedule preview.
    Dynamically recalculates on any parameter change: principal, rate, rate period,
    frequency, installments count, or first payment date.
    """
    try:
        principal = Decimal(request.GET.get('principal', '1000000'))
        interest_rate = Decimal(request.GET.get('interest_rate', '5.0'))
        interest_rate_period = request.GET.get('interest_rate_period', 'MONTHLY')
        interest_type = request.GET.get('interest_type', 'FLAT')
        frequency = request.GET.get('payment_frequency', 'BIWEEKLY')
        total_installments = int(request.GET.get('total_installments', '12'))
        first_date_str = request.GET.get('first_payment_date')
        
        if first_date_str:
            first_payment_date = datetime.datetime.strptime(first_date_str, '%Y-%m-%d').date()
        else:
            # Default first payment date depending on frequency
            today = timezone.localdate()
            if frequency == 'DAILY':
                first_payment_date = today + datetime.timedelta(days=1)
            elif frequency == 'WEEKLY':
                first_payment_date = today + datetime.timedelta(days=7)
            elif frequency == 'BIWEEKLY':
                first_payment_date = today + datetime.timedelta(days=15)
            else:
                first_payment_date = today + datetime.timedelta(days=30)

        schedule = LoanCalculator.generate_schedule(
            principal=principal,
            interest_rate=interest_rate,
            interest_type=interest_type,
            frequency=frequency,
            total_installments=total_installments,
            first_payment_date=first_payment_date,
            interest_rate_period=interest_rate_period
        )
        return render(request, 'loans/partials/simulator_preview.html', {'schedule': schedule, 'error': None})
    except Exception as e:
        return render(request, 'loans/partials/simulator_preview.html', {'schedule': None, 'error': str(e)})


@login_required
def loan_detail_view(request, pk):
    """
    Executive loan detail view.
    Displays contract summary, financial breakdown, customer details,
    and the full persistent installment schedule with payment statuses.
    """
    loan = get_object_or_404(Loan.objects.select_related('customer'), pk=pk)
    installments = loan.installments.all().order_by('installment_number')
    payments = loan.payments.select_related('created_by').order_by('-payment_date', '-created_at')

    return render(request, 'loans/loan_detail.html', {
        'loan': loan,
        'installments': installments,
        'payments': payments,
        'page_title': f"Préstamo {loan.loan_code}",
        'active_nav': 'loans',
    })


@login_required
def installment_list_view(request):
    """
    Global agenda of installments across all active loans.
    Allows filtering by status (PENDING, PAID, OVERDUE), date, and customer.
    """
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date_filter', '').strip() # 'today', 'week', 'month', 'overdue'

    installments_qs = Installment.objects.select_related('loan', 'customer').all().order_by('due_date', 'installment_number')

    today = timezone.localdate()

    if status_filter:
        installments_qs = installments_qs.filter(status=status_filter)

    if query:
        installments_qs = installments_qs.filter(
            Q(customer__first_name__icontains=query) |
            Q(customer__last_name__icontains=query) |
            Q(customer__document_number__icontains=query) |
            Q(loan__loan_code__icontains=query)
        )

    if date_filter == 'today':
        installments_qs = installments_qs.filter(due_date=today)
    elif date_filter == 'week':
        end_week = today + datetime.timedelta(days=7)
        installments_qs = installments_qs.filter(due_date__gte=today, due_date__lte=end_week)
    elif date_filter == 'overdue':
        installments_qs = installments_qs.filter(due_date__lt=today, status__in=['PENDING', 'PARTIAL', 'OVERDUE'])

    # KPI counts
    total_due_today = Installment.objects.filter(due_date=today, status__in=['PENDING', 'PARTIAL']).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    total_overdue = Installment.objects.filter(status='OVERDUE').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    overdue_count = Installment.objects.filter(status='OVERDUE').count()

    paginator = Paginator(installments_qs, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'loans/installment_list.html', {
        'page_title': 'Cronograma de Cuotas',
        'active_nav': 'installments',
        'page_obj': page_obj,
        'installments': page_obj.object_list,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'query': query,
        'today': today,
        'total_due_today': total_due_today,
        'total_overdue': total_overdue,
        'overdue_count': overdue_count,
    })


@login_required
def loan_delete_view(request, pk):
    """
    Delete a loan with mandatory explicit user confirmation.
    Safely cleans up related installments, payments, payment allocations,
    and cash movements within a database transaction.
    """
    loan = get_object_or_404(
        Loan.objects.select_related('customer').prefetch_related('payments', 'installments'),
        pk=pk
    )

    if request.method == 'POST':
        loan_code = loan.loan_code
        customer_name = loan.customer.full_name
        with transaction.atomic():
            # 1. Clean up cash movements linked to this loan or its payments
            payment_receipts = list(loan.payments.values_list('receipt_number', flat=True))
            CashMovement.objects.filter(
                Q(loan_reference=loan_code) | Q(payment_reference__in=payment_receipts)
            ).delete()

            # 2. Delete all payments associated with this loan (this also cascades to PaymentAllocation)
            loan.payments.all().delete()

            # 3. Delete the loan (cascades to Installments and remaining allocations)
            loan.delete()

        messages.success(
            request,
            f"El préstamo {loan_code} del cliente {customer_name} ha sido eliminado definitivamente."
        )
        return redirect('loans:list')

    # GET request: render explicit confirmation page
    total_paid = loan.payments.filter(status='COMPLETED').aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    payments_count = loan.payments.count()
    installments_count = loan.installments.count()

    context = {
        'page_title': f"Confirmar Eliminación — Préstamo {loan.loan_code}",
        'active_nav': 'loans',
        'loan': loan,
        'total_paid': total_paid,
        'payments_count': payments_count,
        'installments_count': installments_count,
    }
    return render(request, 'loans/loan_confirm_delete.html', context)

