from django.contrib import admin
from .models import CashMovement

@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ('movement_type', 'amount', 'movement_date', 'description', 'loan_reference', 'created_at')
    list_filter = ('movement_type', 'movement_date')
    search_fields = ('description', 'loan_reference', 'payment_reference')
    readonly_fields = ('created_at',)

