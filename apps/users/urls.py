from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('perfil/', views.profile_view, name='profile'),
    path('cambiar-contrasena/', auth_views.PasswordChangeView.as_view(
        template_name='users/change_password.html',
        success_url='/auth/perfil/'
    ), name='change_password'),
]

