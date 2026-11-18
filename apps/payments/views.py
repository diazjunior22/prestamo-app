from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def payment_list_view(request):
    return render(request, 'payments/payment_list.html', {'active_nav': 'payments', 'payments': []})

@login_required
def payment_create_view(request):
    return render(request, 'payments/payment_form.html', {'active_nav': 'payments'})
