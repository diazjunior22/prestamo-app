from django import template
from apps.core.utils import format_cop as _format_cop

register = template.Library()

@register.filter(name='cop')
def cop_filter(value, show_cents=False):
    """
    Template filter to format currency as Colombian Pesos.
    Usage: {{ loan.principal|cop }} or {{ loan.balance|cop:True }}
    """
    return _format_cop(value, show_cents=bool(show_cents))

@register.filter(name='percentage')
def percentage_filter(value):
    """
    Formats a decimal or float as percentage.
    Usage: {{ loan.interest_rate|percentage }} -> "5.0%"
    """
    if value is None:
        return "0.0%"
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return f"{value}%"

