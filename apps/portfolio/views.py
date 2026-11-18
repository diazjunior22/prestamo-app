from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def portfolio_view(request):
    return render(request, 'portfolio/portfolio.html', {'active_nav': 'portfolio'})
