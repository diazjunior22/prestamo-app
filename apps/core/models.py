import uuid
from django.db import models

class BaseModel(models.Model):
    """
    Abstract base model providing UUID primary key, timestamp tracking,
    and soft-deletion flag across all financial entities.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Activo")

    class Meta:
        abstract = True
        ordering = ['-created_at']

