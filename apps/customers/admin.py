from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'document_type', 'document_number', 'phone', 'city', 'status', 'created_at')
    list_filter = ('status', 'document_type', 'city')
    search_fields = ('first_name', 'last_name', 'document_number', 'phone', 'whatsapp')
    readonly_fields = ('created_at', 'updated_at')

