from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from apps.cashflow.models import CashAccount, CashMovement, CashReconciliation
from apps.cashflow.forms import (
    CashMovementForm,
    CashTransferForm,
    CashReconciliationForm,
    CashAccountForm,
    CashFilterForm,
)
from apps.cashflow.services.cashflow_service import CashflowService

@login_required
def cashflow_view(request):
    """
    Main cashbook and multi-pocket ledger view.
    Displays accounts (Efectivo, Nequi, Nu, Bancolombia), consolidated balance,
    movements table with progressive tracking, and box reconciliations (arqueos).
    """
    accounts_summary = CashflowService.get_accounts_summary()
    filter_form = CashFilterForm(request.GET or None)

    movements_qs = CashMovement.objects.select_related('account', 'created_by').order_by('-movement_date', '-created_at')

    # Apply filters
    if filter_form.is_valid():
        search = filter_form.cleaned_data.get('search')
        if search:
            search = search.strip()
            movements_qs = movements_qs.filter(
                Q(description__icontains=search) |
                Q(loan_reference__icontains=search) |
                Q(payment_reference__icontains=search) |
                Q(transfer_reference__icontains=search)
            )

        account = filter_form.cleaned_data.get('account')
        if account:
            movements_qs = movements_qs.filter(account=account)

        movement_type = filter_form.cleaned_data.get('movement_type')
        if movement_type:
            movements_qs = movements_qs.filter(movement_type=movement_type)

        date_from = filter_form.cleaned_data.get('date_from')
        if date_from:
            movements_qs = movements_qs.filter(movement_date__gte=date_from)

        date_to = filter_form.cleaned_data.get('date_to')
        if date_to:
            movements_qs = movements_qs.filter(movement_date__lte=date_to)

    # Inflows and Outflows totals
    inflows_total = movements_qs.filter(
        movement_type__in=[
            CashMovement.MovementType.CAPITAL_INJECTION,
            CashMovement.MovementType.PRINCIPAL_RECOVERY,
            CashMovement.MovementType.INTEREST_INCOME,
            CashMovement.MovementType.TRANSFER_IN,
        ]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    outflows_total = movements_qs.filter(
        movement_type__in=[
            CashMovement.MovementType.LOAN_DISBURSEMENT,
            CashMovement.MovementType.EXPENSE,
            CashMovement.MovementType.WITHDRAWAL,
            CashMovement.MovementType.REVERSAL,
            CashMovement.MovementType.TRANSFER_OUT,
        ]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Pagination
    paginator = Paginator(movements_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Recent Reconciliations (Arqueos)
    reconciliations = CashReconciliation.objects.select_related('account', 'created_by').order_by('-reconciliation_date', '-created_at')[:5]

    context = {
        'active_nav': 'cashflow',
        'accounts': accounts_summary['accounts'],
        'total_consolidated': accounts_summary['total_consolidated'],
        'movements': page_obj,
        'page_obj': page_obj,
        'filter_form': filter_form,
        'inflows_total': inflows_total,
        'outflows_total': outflows_total,
        'net_total': inflows_total - outflows_total,
        'reconciliations': reconciliations,
        'movement_form': CashMovementForm(),
        'transfer_form': CashTransferForm(),
        'reconciliation_form': CashReconciliationForm(),
        'account_form': CashAccountForm(),
    }
    return render(request, 'cashflow/cashflow.html', context)


@login_required
def cash_movement_create_view(request):
    """Handles manual movement recording (Capital injection, Expense, Withdrawal)."""
    if request.method == 'POST':
        form = CashMovementForm(request.POST)
        if form.is_valid():
            try:
                CashflowService.record_manual_movement(
                    account=form.cleaned_data['account'],
                    movement_type=form.cleaned_data['movement_type'],
                    amount=form.cleaned_data['amount'],
                    movement_date=form.cleaned_data['movement_date'],
                    description=form.cleaned_data['description'],
                    user=request.user
                )
                messages.success(request, "Movimiento de caja registrado exitosamente.")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
    return redirect('cashflow:index')


@login_required
def cash_transfer_view(request):
    """Handles transfer between pockets (e.g. from Nequi to Nu or Efectivo)."""
    if request.method == 'POST':
        form = CashTransferForm(request.POST)
        if form.is_valid():
            try:
                CashflowService.record_account_transfer(
                    source_account=form.cleaned_data['source_account'],
                    target_account=form.cleaned_data['target_account'],
                    amount=form.cleaned_data['amount'],
                    transfer_date=form.cleaned_data['transfer_date'],
                    notes=form.cleaned_data['notes'],
                    user=request.user
                )
                messages.success(
                    request,
                    f"Transferencia de $ {form.cleaned_data['amount']:,.0f} COP de '{form.cleaned_data['source_account'].name}' a '{form.cleaned_data['target_account'].name}' completada."
                )
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
    return redirect('cashflow:index')


@login_required
def cash_reconciliation_view(request):
    """Handles cash count / app reconciliation audit (Arqueo)."""
    if request.method == 'POST':
        form = CashReconciliationForm(request.POST)
        if form.is_valid():
            try:
                rec = CashflowService.record_reconciliation(
                    account=form.cleaned_data['account'],
                    physical_balance=form.cleaned_data['physical_balance'],
                    notes=form.cleaned_data['notes'],
                    user=request.user
                )
                if rec.difference == Decimal('0.00'):
                    messages.success(request, f"¡Arqueo en '{rec.account.name}' perfecto! Saldo cuadrado exactamente.")
                elif rec.difference > Decimal('0.00'):
                    messages.info(request, f"Arqueo registrado con SOBRANTE de $ {rec.difference:,.2f} COP en '{rec.account.name}'.")
                else:
                    messages.warning(request, f"Arqueo registrado con FALTANTE de $ {abs(rec.difference):,.2f} COP en '{rec.account.name}'.")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
    return redirect('cashflow:index')


@login_required
def cash_account_create_view(request):
    """Creates a new financial pocket or account."""
    if request.method == 'POST':
        form = CashAccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            messages.success(request, f"Bolsillo / Cuenta '{account.name}' creada exitosamente.")
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
    return redirect('cashflow:index')
