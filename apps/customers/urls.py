from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.customer_list_view, name='list'),
    path('nuevo/', views.customer_create_view, name='create'),
    path('api/buscar/', views.customer_search_api_view, name='search_api'),
    path('<uuid:pk>/', views.customer_detail_view, name='detail'),
    path('<uuid:pk>/editar/', views.customer_update_view, name='update'),
    path('<uuid:pk>/cambiar-estado/', views.customer_toggle_status_view, name='toggle_status'),
    path('<uuid:pk>/eliminar/', views.customer_delete_view, name='delete'),
]
