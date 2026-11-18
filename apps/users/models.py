import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Custom user model for LoanManager with UUID primary key,
    role-based authorization support, and phone/avatar fields.
    """
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        COLLECTOR = 'COLLECTOR', 'Cobrador / Operador'
        VIEWER = 'VIEWER', 'Auditor / Solo Lectura'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    phone = models.CharField(max_length=25, blank=True, null=True, verbose_name="Teléfono")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ADMIN,
        verbose_name="Rol en el sistema"
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Foto de perfil")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['first_name', 'last_name']

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.email

