from django.conf import settings

def system_context(request):
    """
    Injects global financial settings, system branding,
    and active navigation helpers into all templates.
    """
    return {
        'SYSTEM_NAME': getattr(settings, 'SYSTEM_NAME', 'LoanManager'),
        'ADMIN_NAME': getattr(settings, 'ADMIN_NAME', 'Administrador'),
        'ADMIN_EMAIL': getattr(settings, 'ADMIN_EMAIL', 'admin@loanmanager.local'),
        'CURRENCY_CODE': getattr(settings, 'CURRENCY_CODE', 'COP'),
        'TIME_ZONE': getattr(settings, 'TIME_ZONE', 'America/Bogota'),
        'unread_notifications_count': 0,
    }

