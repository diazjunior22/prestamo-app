from django.urls import path
from . import views

app_name = 'loans'

urlpatterns = [
    path('', views.loan_list_view, name='list'),
    path('nuevo/', views.loan_create_view, name='create'),
    path('simular/', views.loan_simulate_view, name='simulate'),
    path('cuotas/', views.installment_list_view, name='installments'),
    path('<uuid:pk>/', views.loan_detail_view, name='detail'),
]
