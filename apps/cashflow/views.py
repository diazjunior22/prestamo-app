from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def cashflow_view(request):
    return render(request, 'cashflow/cashflow.html', {'active_nav': 'cashflow', 'movements': []})
