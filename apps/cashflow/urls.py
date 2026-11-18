from django.urls import path
from . import views

app_name = 'cashflow'

urlpatterns = [
    path('', views.cashflow_view, name='index'),
    path('movimiento/crear/', views.cash_movement_create_view, name='movement_create'),
    path('transferir/', views.cash_transfer_view, name='transfer'),
    path('arqueo/', views.cash_reconciliation_view, name='reconciliation'),
    path('cuenta/crear/', views.cash_account_create_view, name='account_create'),
]
