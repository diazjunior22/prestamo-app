from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_list_view, name='list'),
    path('registrar/', views.payment_create_view, name='create'),
]

