from django import forms
from django.utils import timezone
from apps.loans.models import Loan
from apps.payments.models import Payment

class PaymentForm(forms.ModelForm):
    """
    Form to register a new payment or installment collection.
    """
    loan = forms.ModelChoiceField(
        queryset=Loan.objects.filter(status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE]).select_related('customer'),
        label="Préstamo a abonar",
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            'id': 'id_loan'
        })
    )

    class Meta:
        model = Payment
        fields = ['loan', 'amount', 'payment_date', 'payment_method', 'reference_number', 'voucher_image', 'notes']
        widgets = {
            'voucher_image': forms.FileInput(attrs={
                'class': 'hidden',
                'id': 'id_voucher_image',
                'accept': 'image/*,application/pdf'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': '0.00',
                'step': '100',
                'id': 'id_amount'
            }),
            'payment_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            }),
            'payment_method': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            }),
            'reference_number': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': 'Ej. TRX-983728 o N° de recibo físico',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'rows': 2,
                'placeholder': 'Observaciones opcionales...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('payment_date'):
            self.initial['payment_date'] = timezone.localdate()

        # Format loan choices with helpful financial status
        self.fields['loan'].label_from_instance = (
            lambda obj: f"{obj.loan_code} — {obj.customer.full_name} | Saldo: $ {obj.balance:,.0f} COP"
        )

    def clean(self):
        cleaned_data = super().clean()
        loan = cleaned_data.get('loan')
        amount = cleaned_data.get('amount')

        if loan and amount:
            if amount <= 0:
                self.add_error('amount', 'El monto debe ser superior a cero.')
            elif amount > loan.balance:
                self.add_error(
                    'amount',
                    f"El monto no puede superar el saldo pendiente del crédito ($ {loan.balance:,.2f} COP)."
                )
        return cleaned_data


class PaymentFilterForm(forms.Form):
    """Filter form for the payments list."""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar por recibo, cliente, doc o préstamo...',
            'class': 'w-full pl-9 pr-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    payment_method = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los métodos')] + Payment.PaymentMethod.choices,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los estados')] + Payment.Status.choices,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )


class PaymentReversalForm(forms.Form):
    """Reversal confirmation form requiring clear justification."""
    reversal_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-danger-500/20 focus:border-danger-500 focus:bg-white transition',
            'rows': 3,
            'placeholder': 'Describa detalladamente el motivo de la anulación o reversión contable...',
        }),
        min_length=5,
        label="Motivo justificado de reversión"
    )

