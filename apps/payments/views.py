import urllib.parse
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from apps.cashflow.models import CashMovement
from apps.loans.models import Loan, Installment
from apps.payments.models import Payment
from apps.payments.forms import PaymentForm, PaymentFilterForm, PaymentReversalForm
from apps.payments.services.payment_allocator import allocate_payment
from apps.payments.services.payment_reverser import reverse_payment
from apps.payments.services.receipt_generator import build_receipt_pdf_bytes

@login_required
def payment_list_view(request):
    """
    Paginated, searchable, filterable list of all payments and installment collections.
    Displays financial summary metrics (collected this month, collected today, receipt counts).
    """
    filter_form = PaymentFilterForm(request.GET or None)
    payments_qs = Payment.objects.select_related('loan', 'customer', 'created_by').order_by('-payment_date', '-created_at')

    # Apply filters
    if filter_form.is_valid():
        search = filter_form.cleaned_data.get('search')
        if search:
            search = search.strip()
            payments_qs = payments_qs.filter(
                Q(receipt_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__document_number__icontains=search) |
                Q(loan__loan_code__icontains=search) |
                Q(reference_number__icontains=search)
            )

        payment_method = filter_form.cleaned_data.get('payment_method')
        if payment_method:
            payments_qs = payments_qs.filter(payment_method=payment_method)

        status = filter_form.cleaned_data.get('status')
        if status:
            payments_qs = payments_qs.filter(status=status)

        date_from = filter_form.cleaned_data.get('date_from')
        if date_from:
            payments_qs = payments_qs.filter(payment_date__gte=date_from)

        date_to = filter_form.cleaned_data.get('date_to')
        if date_to:
            payments_qs = payments_qs.filter(payment_date__lte=date_to)

    # Calculate summary metrics (only completed payments contribute to metrics)
    today = timezone.localdate()
    first_day_month = today.replace(day=1)

    completed_payments = Payment.objects.filter(status=Payment.Status.COMPLETED)
    
    total_month = completed_payments.filter(
        payment_date__gte=first_day_month,
        payment_date__lte=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_today = completed_payments.filter(
        payment_date=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_receipts_count = completed_payments.count()
    reversed_count = Payment.objects.filter(status=Payment.Status.REVERSED).count()

    # Pagination
    paginator = Paginator(payments_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'active_nav': 'payments',
        'payments': page_obj,
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_month': total_month,
        'total_today': total_today,
        'total_receipts_count': total_receipts_count,
        'reversed_count': reversed_count,
    }

    if request.headers.get('HX-Request') and not request.headers.get('HX-Target') == 'body':
        return render(request, 'payments/partials/payment_table.html', context)

    return render(request, 'payments/payment_list.html', context)


@login_required
def payment_create_view(request):
    """
    Registers a new payment or collection installment.
    Supports pre-filling loan from query string and shows dynamic loan metrics.
    """
    initial_data = {}
    preselected_loan_id = request.GET.get('loan') or request.GET.get('loan_id')
    selected_loan = None

    if preselected_loan_id:
        try:
            selected_loan = Loan.objects.select_related('customer').get(
                id=preselected_loan_id,
                status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE]
            )
            initial_data['loan'] = selected_loan.id
        except (Loan.DoesNotExist, ValueError):
            pass

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            loan = form.cleaned_data['loan']
            amount = form.cleaned_data['amount']
            payment_date = form.cleaned_data['payment_date']
            payment_method = form.cleaned_data['payment_method']
            reference_number = form.cleaned_data['reference_number']
            notes = form.cleaned_data['notes']

            try:
                payment = allocate_payment(
                    loan=loan,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes,
                    user=request.user
                )
                # Auto-dispatch receipt via email if customer has email configured
                try:
                    from apps.notifications.services.email_service import EmailNotificationService
                    if payment.customer.email:
                        EmailNotificationService.send_payment_receipt_email(payment)
                except Exception as ex:
                    import logging
                    logging.getLogger(__name__).warning(f"Error auto-dispatching receipt email: {ex}")

                messages.success(
                    request,
                    f"Recaudo registrado exitosamente: Recibo {payment.receipt_number} por $ {payment.amount:,.0f} COP."
                )
                return redirect('payments:detail', payment_id=payment.id)
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = PaymentForm(initial=initial_data)

    # Next pending installment info if a loan is preselected
    next_installment = None
    if selected_loan:
        next_installment = selected_loan.installments.filter(
            status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL, Installment.Status.OVERDUE]
        ).order_by('installment_number').first()

    context = {
        'active_nav': 'payments',
        'form': form,
        'selected_loan': selected_loan,
        'next_installment': next_installment,
    }
    return render(request, 'payments/payment_form.html', context)


@login_required
def payment_loan_info_view(request, loan_id):
    """
    HTMX endpoint to render loan status badge, remaining balance,
    and quick fill payment buttons when selecting a loan in the payment form.
    """
    try:
        loan = Loan.objects.select_related('customer').get(
            id=loan_id,
            status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE]
        )
    except (Loan.DoesNotExist, ValueError):
        return HttpResponse("")

    next_installment = loan.installments.filter(
        status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL, Installment.Status.OVERDUE]
    ).order_by('installment_number').first()

    context = {
        'loan': loan,
        'next_installment': next_installment,
    }
    return render(request, 'payments/partials/loan_quick_info.html', context)


@login_required
def payment_detail_view(request, payment_id):
    """
    Detailed view of a payment receipt, showing metadata, allocations breakdown,
    PDF download button, WhatsApp share link, and audited reversal modal.
    """
    payment = get_object_or_404(
        Payment.objects.select_related('loan', 'customer', 'created_by', 'reversed_by').prefetch_related(
            'allocations__installment'
        ),
        id=payment_id
    )

    reversal_form = PaymentReversalForm()

    # Pre-generate friendly WhatsApp confirmation text
    customer = payment.customer
    loan = payment.loan
    clean_phone = ''.join(c for c in (customer.whatsapp or customer.phone or '') if c.isdigit())
    if clean_phone.startswith('57') is False and len(clean_phone) == 10:
        clean_phone = f"57{clean_phone}"

    wa_msg = (
        f"Hola {customer.first_name}, te confirmamos el recibido de tu abono por "
        f"$ {payment.amount:,.0f} COP para el crédito {loan.loan_code}. "
        f"Recibo N°: {payment.receipt_number}. Saldo restante: $ {loan.balance:,.0f} COP. "
        f"¡Gracias por tu cumplimiento!"
    )
    whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}" if clean_phone else None

    context = {
        'active_nav': 'payments',
        'payment': payment,
        'allocations': payment.allocations.all(),
        'reversal_form': reversal_form,
        'whatsapp_url': whatsapp_url,
    }
    return render(request, 'payments/payment_detail.html', context)


@login_required
def payment_receipt_pdf_view(request, payment_id):
    """
    Generates or downloads the official PDF receipt on-the-fly.
    """
    payment = get_object_or_404(Payment.objects.select_related('loan', 'customer', 'created_by'), id=payment_id)
    pdf_bytes = build_receipt_pdf_bytes(payment)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Recibo_{payment.receipt_number}.pdf"
    
    # Check if download or inline preview
    if request.GET.get('download') == '1':
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'inline; filename="{filename}"'

    return response


@login_required
def payment_reverse_view(request, payment_id):
    """
    Processes an audited reversal of a completed payment.
    Restricted to ADMIN or authorized users.
    """
    payment = get_object_or_404(Payment.objects.select_related('loan'), id=payment_id)

    # Role check: only ADMIN or superuser can reverse
    if hasattr(request.user, 'role') and request.user.role != 'ADMIN' and not request.user.is_superuser:
        messages.error(request, "Solo los administradores tienen permiso para revertir pagos registrados.")
        return redirect('payments:detail', payment_id=payment.id)

    if request.method == 'POST':
        form = PaymentReversalForm(request.POST)
        if form.is_valid():
            reversal_reason = form.cleaned_data['reversal_reason']
            try:
                reverse_payment(
                    payment=payment,
                    reversal_reason=reversal_reason,
                    user=request.user
                )
                messages.warning(
                    request,
                    f"El recibo {payment.receipt_number} ha sido formalmente reversado. Los saldos del crédito han sido restaurados."
                )
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            messages.error(request, "Debe indicar una justificación válida para proceder con la reversión.")

    return redirect('payments:detail', payment_id=payment.id)


@login_required
def payment_delete_view(request, payment_id):
    """
    Deletes a payment/collection (cobro) record with confirmation.
    Automatically restores the loan balance, installment balances, and cleans
    up the associated cash movements within a database transaction.
    """
    payment = get_object_or_404(
        Payment.objects.select_related('loan', 'customer').prefetch_related('allocations__installment'),
        id=payment_id
    )

    if request.method == 'POST':
        receipt_number = payment.receipt_number
        loan = payment.loan
        loan_code = loan.loan_code

        with transaction.atomic():
            # If payment was COMPLETED, roll back its allocations to installments & loan
            if payment.status == Payment.Status.COMPLETED:
                for alloc in payment.allocations.all():
                    inst = alloc.installment
                    inst.paid_principal = max(Decimal('0.00'), inst.paid_principal - alloc.principal_applied)
                    inst.paid_interest = max(Decimal('0.00'), inst.paid_interest - alloc.interest_applied)
                    inst.paid_at = None
                    today = timezone.localdate()
                    if inst.balance > Decimal('0.00'):
                        inst.status = Installment.Status.OVERDUE if inst.due_date < today else Installment.Status.PENDING
                    inst.save()

                    loan.paid_principal = max(Decimal('0.00'), loan.paid_principal - alloc.principal_applied)
                    loan.paid_interest = max(Decimal('0.00'), loan.paid_interest - alloc.interest_applied)
                    loan.balance += (alloc.principal_applied + alloc.interest_applied)

                # Re-evaluate loan status
                if loan.status == Loan.Status.PAID and loan.balance > Decimal('0.00'):
                    has_overdue = loan.installments.filter(status=Installment.Status.OVERDUE).exists()
                    loan.status = Loan.Status.OVERDUE if has_overdue else Loan.Status.ACTIVE
                loan.save()

            # Clean up CashMovements associated with this receipt
            CashMovement.objects.filter(payment_reference=receipt_number).delete()

            # Delete the payment record (cascades to PaymentAllocation)
            payment.delete()

        messages.success(
            request,
            f"El cobro {receipt_number} ha sido eliminado exitosamente y los saldos del préstamo {loan_code} han sido restaurados."
        )
        return redirect('payments:list')

    # GET request: render confirmation page
    context = {
        'page_title': f"Confirmar Eliminación — Cobro {payment.receipt_number}",
        'active_nav': 'payments',
        'payment': payment,
        'loan': payment.loan,
    }
    return render(request, 'payments/payment_confirm_delete.html', context)


@login_required
def payment_send_receipt_email_view(request, payment_id):
    """Sends or resends the official payment receipt with PDF attachment via email."""
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        custom_email = request.POST.get('recipient_email', '').strip() or None
        from apps.notifications.services.email_service import EmailNotificationService
        success, msg = EmailNotificationService.send_payment_receipt_email(payment, recipient_email=custom_email)
        if success:
            messages.success(request, f"¡Recibo enviado con éxito! {msg}")
        else:
            messages.error(request, f"No se pudo enviar el recibo: {msg}")
    return redirect('payments:detail', payment_id=payment.id)


