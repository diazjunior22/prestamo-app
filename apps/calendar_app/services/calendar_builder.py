import calendar
import datetime
from decimal import Decimal
from django.utils import timezone
from apps.loans.models import Installment

SPANISH_MONTHS = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
]

SPANISH_WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

class CalendarBuilder:
    """
    Builds structured calendar grid data and financial metrics for collection agendas.
    """

    @classmethod
    def get_month_data(cls, year: int, month: int, today=None, status_filter: str = 'ALL') -> dict:
        if today is None:
            today = timezone.localdate()

        # Generate weeks (Monday to Sunday)
        cal = calendar.Calendar(firstweekday=0)
        month_matrix = cal.monthdatescalendar(year, month)

        start_date = month_matrix[0][0]
        end_date = month_matrix[-1][-1]

        # Query all scheduled installments in visible grid range
        installments_qs = Installment.objects.filter(
            due_date__gte=start_date,
            due_date__lte=end_date,
            is_active=True
        ).select_related('customer', 'loan')

        # Status filter if requested
        if status_filter == 'PENDING':
            installments_qs = installments_qs.filter(balance__gt=0)
        elif status_filter == 'OVERDUE':
            installments_qs = installments_qs.filter(
                status=Installment.Status.OVERDUE
            ) | installments_qs.filter(due_date__lt=today, balance__gt=0)
        elif status_filter == 'PAID':
            installments_qs = installments_qs.filter(status=Installment.Status.PAID)

        # Group installments by due_date
        days_map = {}
        for inst in installments_qs:
            d = inst.due_date
            if d not in days_map:
                days_map[d] = {
                    'installments': [],
                    'total_amount': Decimal('0.00'),
                    'total_balance': Decimal('0.00'),
                    'total_paid': Decimal('0.00'),
                    'has_overdue': False,
                    'has_pending': False,
                    'all_paid': True,
                    'count': 0,
                }
            days_map[d]['installments'].append(inst)
            days_map[d]['total_amount'] += inst.total_amount
            days_map[d]['total_balance'] += inst.balance
            days_map[d]['total_paid'] += (inst.paid_principal + inst.paid_interest)
            days_map[d]['count'] += 1

            if inst.status == Installment.Status.OVERDUE or (inst.due_date < today and inst.balance > Decimal('0.00')):
                days_map[d]['has_overdue'] = True

            if inst.balance > Decimal('0.00'):
                days_map[d]['has_pending'] = True
                days_map[d]['all_paid'] = False

        # Build grid with metadata
        weeks_data = []
        month_total_due = Decimal('0.00')
        month_total_collected = Decimal('0.00')
        month_total_pending = Decimal('0.00')
        month_total_overdue = Decimal('0.00')
        month_installments_count = 0

        for week in month_matrix:
            week_days = []
            for day_date in week:
                is_curr_month = (day_date.month == month and day_date.year == year)
                is_today = (day_date == today)
                is_past = (day_date < today)
                day_info = days_map.get(day_date)

                if day_info:
                    count = day_info['count']
                    total_amount = day_info['total_amount']
                    total_balance = day_info['total_balance']
                    total_paid = day_info['total_paid']
                    has_overdue = day_info['has_overdue']
                    has_pending = day_info['has_pending']
                    all_paid = day_info['all_paid']

                    # Color badge selection
                    if has_overdue:
                        status_color = 'rose'
                    elif is_today and has_pending:
                        status_color = 'amber'
                    elif has_pending and not is_past:
                        status_color = 'blue'
                    elif all_paid and count > 0:
                        status_color = 'emerald'
                    else:
                        status_color = 'slate'

                    # Aggregate monthly totals only for days inside the selected month
                    if is_curr_month:
                        month_total_due += total_amount
                        month_total_collected += total_paid
                        month_total_pending += total_balance
                        month_installments_count += count
                        if has_overdue:
                            month_total_overdue += total_balance
                else:
                    count = 0
                    total_amount = Decimal('0.00')
                    total_balance = Decimal('0.00')
                    total_paid = Decimal('0.00')
                    has_overdue = False
                    has_pending = False
                    all_paid = False
                    status_color = None

                week_days.append({
                    'date': day_date,
                    'day': day_date.day,
                    'date_str': day_date.strftime('%Y-%m-%d'),
                    'is_current_month': is_curr_month,
                    'is_today': is_today,
                    'is_past': is_past,
                    'count': count,
                    'total_amount': total_amount,
                    'total_balance': total_balance,
                    'total_paid': total_paid,
                    'has_overdue': has_overdue,
                    'has_pending': has_pending,
                    'all_paid': all_paid,
                    'status_color': status_color,
                })
            weeks_data.append(week_days)

        # Previous and Next Month navigation
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year

        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        return {
            'year': year,
            'month': month,
            'month_name': SPANISH_MONTHS[month],
            'prev_year': prev_year,
            'prev_month': prev_month,
            'next_year': next_year,
            'next_month': next_month,
            'weeks': weeks_data,
            'weekdays': SPANISH_WEEKDAYS,
            'month_total_due': month_total_due,
            'month_total_collected': month_total_collected,
            'month_total_pending': month_total_pending,
            'month_total_overdue': month_total_overdue,
            'month_installments_count': month_installments_count,
        }

    @classmethod
    def get_day_agenda(cls, target_date: datetime.date) -> dict:
        """
        Retrieves all scheduled commitments for a specific date,
        calculates financial summaries and constructs WhatsApp reminder URLs.
        """
        today = timezone.localdate()
        installments = list(
            Installment.objects.filter(
                due_date=target_date,
                is_active=True
            ).select_related('customer', 'loan').order_by('customer__last_name', 'installment_number')
        )

        total_due = Decimal('0.00')
        total_balance = Decimal('0.00')
        total_paid = Decimal('0.00')
        overdue_count = 0

        enhanced_installments = []
        for inst in installments:
            total_due += inst.total_amount
            total_balance += inst.balance
            total_paid += (inst.paid_principal + inst.paid_interest)

            is_overdue = (inst.status == Installment.Status.OVERDUE) or (target_date < today and inst.balance > Decimal('0.00'))
            if is_overdue:
                overdue_count += 1

            # Prepare WhatsApp message
            customer = inst.customer
            clean_phone = ''.join(c for c in (customer.whatsapp or customer.phone or '') if c.isdigit())
            if clean_phone and not clean_phone.startswith('57') and len(clean_phone) == 10:
                clean_phone = f"57{clean_phone}"

            if is_overdue:
                wa_msg = (
                    f"Estimado/a {customer.first_name}, le informamos que su cuota #{inst.installment_number} "
                    f"por valor de $ {inst.balance:,.0f} COP del crédito {inst.loan.loan_code} presenta mora. "
                    f"Agradecemos ponerse al día a la mayor brevedad posible."
                )
            else:
                wa_msg = (
                    f"Hola {customer.first_name}, recordatorio de pago: su cuota #{inst.installment_number} "
                    f"por valor de $ {inst.balance:,.0f} COP del crédito {inst.loan.loan_code} "
                    f"tiene vencimiento programado para hoy ({target_date.strftime('%d/%m/%Y')}). ¡Gracias por su cumplimiento!"
                )

            import urllib.parse
            whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}" if clean_phone else None

            enhanced_installments.append({
                'installment': inst,
                'customer': customer,
                'loan': inst.loan,
                'is_overdue': is_overdue,
                'whatsapp_url': whatsapp_url,
            })

        return {
            'target_date': target_date,
            'is_today': (target_date == today),
            'is_past': (target_date < today),
            'installments': enhanced_installments,
            'total_count': len(installments),
            'overdue_count': overdue_count,
            'total_due': total_due,
            'total_balance': total_balance,
            'total_paid': total_paid,
        }
