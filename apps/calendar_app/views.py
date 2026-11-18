from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def calendar_view(request):
    return render(request, 'calendar_app/calendar.html', {'active_nav': 'calendar'})

