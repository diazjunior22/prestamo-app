"""
Root URL configuration for LoanManager.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('apps.users.urls', namespace='users')),
    path('', include('apps.core.urls', namespace='core')),
    path('clientes/', include('apps.customers.urls', namespace='customers')),
    path('prestamos/', include('apps.loans.urls', namespace='loans')),
    path('pagos/', include('apps.payments.urls', namespace='payments')),
    path('caja/', include('apps.cashflow.urls', namespace='cashflow')),
    path('cartera/', include('apps.portfolio.urls', namespace='portfolio')),
    path('calendario/', include('apps.calendar_app.urls', namespace='calendar_app')),
    path('notificaciones/', include('apps.notifications.urls', namespace='notifications')),
    path('reportes/', include('apps.reports.urls', namespace='reports')),
    path('auditoria/', include('apps.audit.urls', namespace='audit')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
