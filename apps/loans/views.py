from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def loan_list_view(request):
    return render(request, 'loans/loan_list.html', {'active_nav': 'loans', 'loans': []})

@login_required
def loan_create_view(request):
    return render(request, 'loans/loan_form.html', {'active_nav': 'loans'})

@login_required
def installment_list_view(request):
    return render(request, 'loans/installment_list.html', {'active_nav': 'installments', 'installments': []})

