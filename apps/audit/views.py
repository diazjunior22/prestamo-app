from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def audit_log_view(request):
    return render(request, 'audit/audit_log.html', {'active_nav': 'audit', 'logs': []})

