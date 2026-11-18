from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def report_list_view(request):
    return render(request, 'reports/report_list.html', {'active_nav': 'reports'})

