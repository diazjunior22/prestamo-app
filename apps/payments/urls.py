from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_list_view, name='list'),
    path('registrar/', views.payment_create_view, name='create'),
    path('prestamo-info/<uuid:loan_id>/', views.payment_loan_info_view, name='loan_info'),
    path('<uuid:payment_id>/', views.payment_detail_view, name='detail'),
    path('<uuid:payment_id>/recibo/', views.payment_receipt_pdf_view, name='receipt_pdf'),
    path('<uuid:payment_id>/enviar-correo/', views.payment_send_receipt_email_view, name='send_email'),
    path('<uuid:payment_id>/revertir/', views.payment_reverse_view, name='reverse'),
    path('<uuid:payment_id>/eliminar/', views.payment_delete_view, name='delete'),
]
