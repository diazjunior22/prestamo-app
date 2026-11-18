import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from apps.core.services.dashboard_service import DashboardService

@login_required
def dashboard_view(request):
    """
    Main executive dashboard for LoanManager.
    Displays real-time financial KPIs, portfolio summary, cash status,
    upcoming due installments, alerts, and recent transactions.
    """
    today = timezone.localdate()

    kpis = DashboardService.get_kpis(today=today)
    chart_flow = DashboardService.get_chart_flow_data(year=today.year)
    portfolio_health = DashboardService.get_portfolio_health(today=today)
    upcoming_installments = DashboardService.get_upcoming_installments(today=today, limit=8)
    recent_activities = DashboardService.get_recent_activities(limit=6)

    context = {
        'page_title': 'Dashboard Financiero',
        'kpis': kpis,
        'today': today,
        'chart_flow': chart_flow,
        'chart_flow_json': json.dumps(chart_flow),
        'portfolio_health': portfolio_health,
        'portfolio_health_json': json.dumps(portfolio_health),
        'upcoming_installments': upcoming_installments,
        'recent_activities': recent_activities,
        'active_nav': 'dashboard',
    }
    return render(request, 'core/dashboard.html', context)
