import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from apps.calendar_app.services.calendar_builder import CalendarBuilder

@login_required
def calendar_view(request):
    """
    Main collection calendar view.
    Displays month grid with financial indicators and side agenda for the selected day.
    """
    today = timezone.localdate()

    # Parse year and month
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            month = today.month
        if not (2020 <= year <= 2040):
            year = today.year
    except (ValueError, TypeError):
        year = today.year
        month = today.month

    # Selected date
    date_param = request.GET.get('date') or request.GET.get('selected_date')
    if date_param:
        try:
            selected_date = datetime.datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        # Default to today if current month/year matches, else first day of month
        if year == today.year and month == today.month:
            selected_date = today
        else:
            selected_date = datetime.date(year, month, 1)

    status_filter = request.GET.get('status', 'ALL').upper()
    if status_filter not in ['ALL', 'PENDING', 'OVERDUE', 'PAID']:
        status_filter = 'ALL'

    calendar_data = CalendarBuilder.get_month_data(
        year=year,
        month=month,
        today=today,
        status_filter=status_filter
    )

    day_agenda = CalendarBuilder.get_day_agenda(target_date=selected_date)

    context = {
        'active_nav': 'calendar',
        'calendar_data': calendar_data,
        'day_agenda': day_agenda,
        'selected_date': selected_date,
        'status_filter': status_filter,
        'today': today,
    }
    return render(request, 'calendar_app/calendar.html', context)


@login_required
def day_agenda_view(request, date_str):
    """
    HTMX partial view to load the agenda commitments for a clicked day.
    """
    try:
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        target_date = timezone.localdate()

    day_agenda = CalendarBuilder.get_day_agenda(target_date=target_date)

    context = {
        'day_agenda': day_agenda,
        'selected_date': target_date,
    }
    return render(request, 'calendar_app/partials/day_agenda.html', context)
