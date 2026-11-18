from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list_view, name='list'),
    path('test/', views.notification_send_test_view, name='send_test'),
    path('trigger-reminders/', views.notification_trigger_reminders_view, name='trigger_reminders'),
    path('trigger-digest/', views.notification_trigger_digest_view, name='trigger_digest'),
    path('logs/<uuid:pk>/preview/', views.notification_detail_modal_view, name='log_preview'),
]
