from decimal import Decimal
from django import forms
from django.utils import timezone
from apps.customers.models import Customer
from .models import Loan

INPUT_CLASSES = (
    "w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-slate-900 "
    "placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent "
    "text-sm transition shadow-2xs"
)

SELECT_CLASSES = (
    "w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-slate-900 "
    "focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm transition shadow-2xs"
)

TEXTAREA_CLASSES = (
    "w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-slate-900 "
    "placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent "
    "text-sm transition shadow-2xs resize-none"
)

class LoanForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(status=Customer.Status.ACTIVE),
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
        empty_label="-- Selecciona un prestatario --",
        label="Cliente Prestatario"
    )

    class Meta:
        model = Loan
        fields = [
            'customer',
            'principal',
            'interest_type',
            'interest_rate',
            'payment_frequency',
            'total_installments',
            'disbursement_date',
            'first_payment_date',
            'notes',
        ]
        widgets = {
            'principal': forms.NumberInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'Ej. 1000000',
                'min': '10000',
                'step': '1000',
            }),
            'interest_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'interest_rate': forms.NumberInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'Ej. 5.0',
                'min': '0',
                'max': '100',
                'step': '0.1',
            }),
            'payment_frequency': forms.Select(attrs={'class': SELECT_CLASSES}),
            'total_installments': forms.NumberInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'Ej. 12',
                'min': '1',
                'max': '360',
            }),
            'disbursement_date': forms.DateInput(attrs={
                'class': INPUT_CLASSES,
                'type': 'date',
            }),
            'first_payment_date': forms.DateInput(attrs={
                'class': INPUT_CLASSES,
                'type': 'date',
            }),
            'notes': forms.Textarea(attrs={
                'class': TEXTAREA_CLASSES,
                'rows': 2,
                'placeholder': 'Garantías, acuerdos especiales, motivo del préstamo...'
            }),
        }

    def __init__(self, *args, **kwargs):
        initial_customer_id = kwargs.pop('initial_customer_id', None)
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.initial.get('disbursement_date'):
            self.initial['disbursement_date'] = today.strftime('%Y-%m-%d')
        if not self.initial.get('first_payment_date'):
            self.initial['first_payment_date'] = (today + timezone.timedelta(days=30)).strftime('%Y-%m-%d')
        if not self.initial.get('interest_rate'):
            self.initial['interest_rate'] = '5.0'
        if not self.initial.get('total_installments'):
            self.initial['total_installments'] = '6'

        if initial_customer_id:
            self.initial['customer'] = initial_customer_id

    def clean_principal(self):
        principal = self.cleaned_data.get('principal')
        if not principal or principal < Decimal('10000.00'):
            raise forms.ValidationError("El capital mínimo para desembolso es de $ 10.000 COP.")
        return principal

    def clean_total_installments(self):
        installments = self.cleaned_data.get('total_installments')
        if not installments or installments <= 0:
            raise forms.ValidationError("Debe indicar al menos 1 cuota.")
        if installments > 360:
            raise forms.ValidationError("El número máximo de cuotas permitido es 360.")
        return installments

    def clean(self):
        cleaned_data = super().clean()
        disbursement = cleaned_data.get('disbursement_date')
        first_payment = cleaned_data.get('first_payment_date')

        if disbursement and first_payment:
            if first_payment < disbursement:
                self.add_error('first_payment_date', "La fecha del primer pago no puede ser anterior a la fecha de desembolso.")

        return cleaned_data

