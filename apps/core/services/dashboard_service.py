import datetime
import urllib.parse
from decimal import Decimal
from django.db.models import Sum, Q, F
from django.utils import timezone

from apps.loans.models import Loan, Installment
from apps.payments.models import Payment, PaymentAllocation
from apps.cashflow.models import CashMovement

class DashboardService:
    """
    Financial aggregation service for the executive SaaS dashboard.
    Computes real-time KPIs, historical flow trends, portfolio risk distributions,
    upcoming collection agenda, and unified activity feed.
    """

    @classmethod
    def get_kpis(cls, today=None) -> dict:
        if today is None:
            today = timezone.localdate()

        # 1. Real Available Liquid Cash
        available_capital = CashMovement.get_current_balance()

        # Active & Overdue loans
        active_loans = Loan.objects.filter(
            status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE],
            is_active=True
        )

        # 2. Capital colocado en circulación
        lent_capital = active_loans.aggregate(total=Sum('principal'))['total'] or Decimal('0.00')

        # 3. Capital pendiente por cobrar (Principal neto)
        # sum(principal) - sum(paid_principal) across active loans
        lent_totals = active_loans.aggregate(
            total_principal=Sum('principal'),
            total_paid_principal=Sum('paid_principal')
        )
        total_p = lent_totals['total_principal'] or Decimal('0.00')
        total_pp = lent_totals['total_paid_principal'] or Decimal('0.00')
        pending_principal = max(Decimal('0.00'), total_p - total_pp)

        # 4. Intereses cobrados reales (recaudos netos completados)
        collected_interest = PaymentAllocation.objects.filter(
            payment__status=Payment.Status.COMPLETED
        ).aggregate(total=Sum('interest_applied'))['total'] or Decimal('0.00')

        # 5. Intereses proyectados pendientes por cobrar
        unpaid_installments = Installment.objects.filter(
            loan__status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE],
            is_active=True
        )
        inst_interest_totals = unpaid_installments.aggregate(
            total_interest=Sum('interest_amount'),
            total_paid_interest=Sum('paid_interest')
        )
        total_i = inst_interest_totals['total_interest'] or Decimal('0.00')
        total_pi = inst_interest_totals['total_paid_interest'] or Decimal('0.00')
        pending_interest = max(Decimal('0.00'), total_i - total_pi)

        # 6. Cobros exigibles hoy (saldo de cuotas que vencen hoy y aún no están totalmente pagadas)
        today_due_amount = Installment.objects.filter(
            due_date=today,
            balance__gt=0,
            is_active=True
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

        # 7. Préstamos activos
        active_loans_count = active_loans.count()

        # 8. Cuotas vencidas (en mora)
        overdue_installments_count = Installment.objects.filter(
            Q(status=Installment.Status.OVERDUE) | Q(due_date__lt=today, balance__gt=0),
            is_active=True
        ).count()

        return {
            'available_capital': available_capital,
            'lent_capital': lent_capital,
            'pending_principal': pending_principal,
            'collected_interest': collected_interest,
            'pending_interest': pending_interest,
            'today_due_amount': today_due_amount,
            'active_loans_count': active_loans_count,
            'overdue_installments_count': overdue_installments_count,
        }

    @classmethod
    def get_chart_flow_data(cls, year=None) -> dict:
        """
        Calculates monthly disbursements vs collections for the given year (12 months).
        """
        if year is None:
            year = timezone.localdate().year

        month_labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        disbursements = [0.0] * 12
        collections = [0.0] * 12

        # Inflows: Principal recovery + interest income
        inflows_qs = CashMovement.objects.filter(
            movement_date__year=year,
            movement_type__in=[
                CashMovement.MovementType.PRINCIPAL_RECOVERY,
                CashMovement.MovementType.INTEREST_INCOME
            ],
            is_active=True
        ).values('movement_date__month').annotate(total=Sum('amount'))

        for item in inflows_qs:
            m = item['movement_date__month']
            if 1 <= m <= 12:
                collections[m - 1] = float(item['total'])

        # Outflows: Loan disbursements
        outflows_qs = CashMovement.objects.filter(
            movement_date__year=year,
            movement_type=CashMovement.MovementType.LOAN_DISBURSEMENT,
            is_active=True
        ).values('movement_date__month').annotate(total=Sum('amount'))

        for item in outflows_qs:
            m = item['movement_date__month']
            if 1 <= m <= 12:
                disbursements[m - 1] = float(item['total'])

        return {
            'labels': month_labels,
            'disbursements': disbursements,
            'collections': collections,
            'year': year,
        }

    @classmethod
    def get_portfolio_health(cls, today=None) -> dict:
        """
        Calculates portfolio risk segments based on days of overdue delinquency:
        - Al día (0 días de mora: due_date >= today o balance == 0)
        - Atraso leve (1 a 30 días de mora)
        - Mora crítica (> 30 días de mora)
        """
        if today is None:
            today = timezone.localdate()

        active_installments = Installment.objects.filter(
            loan__status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE],
            balance__gt=0,
            is_active=True
        )

        total_pending = active_installments.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

        if total_pending == Decimal('0.00'):
            return {
                'on_time_pct': 100.0,
                'mild_delay_pct': 0.0,
                'critical_delay_pct': 0.0,
                'donut_data': [100.0, 0.0, 0.0],
            }

        # 1. On time: due_date >= today
        on_time_amt = active_installments.filter(due_date__gte=today).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0.00')

        # 2. Mild delay: due_date < today and due_date >= today - 30 days
        cutoff_30 = today - datetime.timedelta(days=30)
        mild_amt = active_installments.filter(
            due_date__lt=today,
            due_date__gte=cutoff_30
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

        # 3. Critical delay: due_date < today - 30 days
        critical_amt = active_installments.filter(
            due_date__lt=cutoff_30
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

        on_time_pct = round(float((on_time_amt / total_pending) * 100), 1)
        mild_delay_pct = round(float((mild_amt / total_pending) * 100), 1)
        critical_delay_pct = round(float((critical_amt / total_pending) * 100), 1)

        return {
            'on_time_pct': on_time_pct,
            'mild_delay_pct': mild_delay_pct,
            'critical_delay_pct': critical_delay_pct,
            'donut_data': [on_time_pct, mild_delay_pct, critical_delay_pct],
        }

    @classmethod
    def get_upcoming_installments(cls, today=None, limit=8) -> list:
        """
        Returns cuotas scheduled for collection today or in the next 7 days,
        plus any overdue cuotas needing immediate collection action.
        """
        if today is None:
            today = timezone.localdate()

        # Prioritize overdue first, then today, then upcoming within next 7 days
        next_week = today + datetime.timedelta(days=7)
        qs = Installment.objects.filter(
            due_date__lte=next_week,
            balance__gt=0,
            is_active=True
        ).select_related('customer', 'loan').order_by('due_date', 'customer__last_name')[:limit]

        results = []
        for inst in qs:
            is_overdue = (inst.due_date < today)
            is_today = (inst.due_date == today)

            # WhatsApp direct reminder link
            clean_phone = ''.join(c for c in (inst.customer.whatsapp or inst.customer.phone or '') if c.isdigit())
            if clean_phone and not clean_phone.startswith('57') and len(clean_phone) == 10:
                clean_phone = f"57{clean_phone}"

            if is_overdue:
                wa_msg = (
                    f"Hola {inst.customer.first_name}, tu cuota #{inst.installment_number} "
                    f"por $ {inst.balance:,.0f} COP del crédito {inst.loan.loan_code} presenta mora. "
                    f"Te invitamos a ponerte al día hoy."
                )
            else:
                wa_msg = (
                    f"Hola {inst.customer.first_name}, recordatorio: hoy vence tu cuota #{inst.installment_number} "
                    f"por $ {inst.balance:,.0f} COP del crédito {inst.loan.loan_code}. ¡Gracias por tu puntualidad!"
                )
            whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}" if clean_phone else None

            results.append({
                'id': inst.id,
                'customer_name': inst.customer.full_name,
                'customer_id': inst.customer.id,
                'loan_code': inst.loan.loan_code,
                'loan_id': inst.loan.id,
                'installment_number': inst.installment_number,
                'due_date': inst.due_date,
                'amount': inst.balance,
                'status': 'En Mora' if is_overdue else ('Vence Hoy' if is_today else 'Pendiente'),
                'is_overdue': is_overdue,
                'is_today': is_today,
                'whatsapp_url': whatsapp_url,
            })
        return results

    @classmethod
    def get_recent_activities(cls, limit=6) -> list:
        """
        Combines recent loan disbursements and incoming payments into a unified activity feed.
        """
        activities = []

        # Recent Loans
        recent_loans = Loan.objects.select_related('customer').order_by('-created_at')[:limit]
        for loan in recent_loans:
            activities.append({
                'description': f"Desembolso {loan.loan_code}: $ {loan.principal:,.0f} COP a {loan.customer.full_name}",
                'timestamp': loan.created_at,
                'type': 'loan',
                'url': f"/prestamos/{loan.id}/",
                'icon': 'banknote',
                'color': 'blue',
            })

        # Recent Payments
        recent_payments = Payment.objects.select_related('customer', 'loan').order_by('-created_at')[:limit]
        for p in recent_payments:
            if p.is_reversed:
                activities.append({
                    'description': f"Reversión de pago {p.receipt_number}: $ {p.amount:,.0f} COP ({p.customer.full_name})",
                    'timestamp': p.updated_at,
                    'type': 'reversal',
                    'url': f"/pagos/{p.id}/",
                    'icon': 'rotate-ccw',
                    'color': 'rose',
                })
            else:
                activities.append({
                    'description': f"Recaudo {p.receipt_number}: $ {p.amount:,.0f} COP de {p.customer.full_name}",
                    'timestamp': p.created_at,
                    'type': 'payment',
                    'url': f"/pagos/{p.id}/",
                    'icon': 'receipt',
                    'color': 'emerald',
                })

        # Sort combined activities by timestamp descending
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:limit]
