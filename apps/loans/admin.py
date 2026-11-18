from django.contrib import admin
from .models import Loan, Installment

class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    readonly_fields = ('installment_number', 'due_date', 'principal_amount', 'interest_amount', 'total_amount', 'paid_principal', 'paid_interest', 'balance', 'status')
    can_delete = False

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('loan_code', 'customer', 'principal', 'interest_rate', 'total_amount', 'balance', 'status', 'disbursement_date')
    list_filter = ('status', 'interest_type', 'payment_frequency')
    search_fields = ('loan_code', 'customer__first_name', 'customer__last_name', 'customer__document_number')
    readonly_fields = ('loan_code', 'total_interest', 'total_amount', 'paid_principal', 'paid_interest', 'balance', 'created_at')
    inlines = [InstallmentInline]

@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ('loan', 'installment_number', 'customer', 'due_date', 'total_amount', 'balance', 'status')
    list_filter = ('status', 'due_date')
    search_fields = ('loan__loan_code', 'customer__first_name', 'customer__last_name', 'customer__document_number')

