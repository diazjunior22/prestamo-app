from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Customer
from .forms import CustomerForm, CustomerFilterForm

@login_required
def customer_list_view(request):
    """
    List customers with instant HTMX search by name, document or phone,
    filtering by status, and full pagination.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    customers_qs = Customer.objects.all().order_by('-created_at')

    if query:
        customers_qs = customers_qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(document_number__icontains=query) |
            Q(phone__icontains=query) |
            Q(whatsapp__icontains=query)
        )

    if status_filter:
        customers_qs = customers_qs.filter(status=status_filter)

    # Global KPI counters for the header pills
    total_count = Customer.objects.count()
    active_count = Customer.objects.filter(status=Customer.Status.ACTIVE).count()
    blocked_count = Customer.objects.filter(status=Customer.Status.BLOCKED).count()

    paginator = Paginator(customers_qs, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    filter_form = CustomerFilterForm(initial={'q': query, 'status': status_filter})

    context = {
        'page_title': 'Directorio de Clientes',
        'active_nav': 'customers',
        'page_obj': page_obj,
        'customers': page_obj.object_list,
        'filter_form': filter_form,
        'query': query,
        'status_filter': status_filter,
        'total_count': total_count,
        'active_count': active_count,
        'blocked_count': blocked_count,
    }

    # If requested by HTMX, return only the table partial
    if request.headers.get('HX-Request'):
        return render(request, 'customers/partials/customer_table.html', context)

    return render(request, 'customers/customer_list.html', context)


@login_required
def customer_create_view(request):
    """
    Form view to create a new borrower.
    Validates mandatory name, document, phone, and ensures uniqueness.
    """
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, f"Cliente {customer.full_name} registrado exitosamente.")
            return redirect('customers:detail', pk=customer.pk)
        else:
            messages.error(request, "Por favor corrige los errores señalados en el formulario.")
    else:
        form = CustomerForm()

    return render(request, 'customers/customer_form.html', {
        'form': form,
        'page_title': 'Registrar Nuevo Cliente',
        'active_nav': 'customers',
        'is_edit': False,
    })


@login_required
def customer_detail_view(request, pk):
    """
    Detailed profile view for a customer.
    Shows personal contact channels, direct WhatsApp link,
    summary of loan history, and payment compliance score.
    """
    customer = get_object_or_404(Customer, pk=pk)

    # Loans and recent payments for this customer
    loans = customer.loans.all().order_by('-created_at') if hasattr(customer, 'loans') else []
    payments = customer.payments.select_related('loan').order_by('-payment_date', '-created_at')[:10] if hasattr(customer, 'payments') else []

    context = {
        'page_title': customer.full_name,
        'active_nav': 'customers',
        'customer': customer,
        'loans': loans,
        'payments': payments,
    }
    return render(request, 'customers/customer_detail.html', context)


@login_required
def customer_update_view(request, pk):
    """
    Edit existing customer information.
    """
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Datos de {customer.full_name} actualizados correctamente.")
            return redirect('customers:detail', pk=customer.pk)
        else:
            messages.error(request, "Por favor corrige los errores señalados en el formulario.")
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/customer_form.html', {
        'form': form,
        'customer': customer,
        'page_title': f"Editar Cliente — {customer.full_name}",
        'active_nav': 'customers',
        'is_edit': True,
    })


@login_required
def customer_toggle_status_view(request, pk):
    """
    Safely deactivate or reactivate a customer.
    Guarantees that a customer with active unpaid loans cannot be deactivated.
    """
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        if customer.status == Customer.Status.ACTIVE:
            # Check if has active loans
            if customer.get_active_loans_count() > 0:
                messages.error(request, f"No puedes desactivar a {customer.full_name} porque tiene préstamos activos vigentes.")
                return redirect('customers:detail', pk=customer.pk)
            customer.status = Customer.Status.INACTIVE
            customer.save()
            messages.warning(request, f"El cliente {customer.full_name} ha sido marcado como INACTIVO.")
        else:
            customer.status = Customer.Status.ACTIVE
            customer.save()
            messages.success(request, f"El cliente {customer.full_name} ha sido reactivado.")

    return redirect('customers:detail', pk=customer.pk)
