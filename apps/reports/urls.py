from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list_view, name='list'),
    path('backup/exportar/', views.backup_export_view, name='backup_export'),
    path('backup/restaurar/', views.backup_restore_view, name='backup_restore'),
]

