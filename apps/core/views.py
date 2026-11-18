from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

@login_required
def dashboard_view(request):
    """
    Main executive dashboard for LoanManager.
    Displays real-time financial KPIs, portfolio summary, cash status,
    upcoming due installments, alerts, and recent transactions.
    """
    today = timezone.localdate()

    # Financial KPIs (Starting clean state or aggregations)
    kpis = {
        'available_capital': Decimal('0.00'),       # Dinero real disponible en caja
        'lent_capital': Decimal('0.00'),            # Capital total colocado históricamente
        'pending_principal': Decimal('0.00'),       # Capital que aún deben los clientes
        'pending_interest': Decimal('0.00'),        # Intereses pactados pendientes de cobro
        'collected_interest': Decimal('0.00'),      # Rendimientos reales ya cobrados
        'active_loans_count': 0,                    # Cantidad de préstamos vigentes
        'overdue_installments_count': 0,            # Cuotas con fecha vencida sin pago
        'today_due_amount': Decimal('0.00'),        # Valor total exigible el día de hoy
    }

    context = {
        'page_title': 'Dashboard Financiero',
        'kpis': kpis,
        'today': today,
        'upcoming_installments': [],
        'recent_activities': [],
        'active_nav': 'dashboard',
    }
    return render(request, 'core/dashboard.html', context)
