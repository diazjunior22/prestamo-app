from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def customer_list_view(request):
    return render(request, 'customers/customer_list.html', {'active_nav': 'customers', 'customers': []})
