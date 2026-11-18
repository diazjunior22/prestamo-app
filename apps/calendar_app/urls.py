from django.urls import path
from . import views

app_name = 'calendar_app'

urlpatterns = [
    path('', views.calendar_view, name='index'),
    path('agenda/<str:date_str>/', views.day_agenda_view, name='day_agenda'),
]
