from django import forms
from django.utils import timezone
from apps.cashflow.models import CashAccount, CashMovement, CashReconciliation

class CashMovementForm(forms.ModelForm):
    """
    Form to record manual cash movements (Capital Injection, Operational Expense, Owner Withdrawal).
    """
    MANUAL_TYPE_CHOICES = [
        (CashMovement.MovementType.CAPITAL_INJECTION, 'Aporte de Capital (+)'),
        (CashMovement.MovementType.EXPENSE, 'Gasto Operativo (-)'),
        (CashMovement.MovementType.WITHDRAWAL, 'Retiro de Dinero (-)'),
    ]

    movement_type = forms.ChoiceField(
        choices=MANUAL_TYPE_CHOICES,
        label="Tipo de movimiento",
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )

    class Meta:
        model = CashMovement
        fields = ['account', 'movement_type', 'amount', 'movement_date', 'description']
        widgets = {
            'account': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': '0.00',
                'step': '100',
            }),
            'movement_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            }),
            'description': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': 'Concepto o justificación del movimiento...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CashAccount.ensure_default_accounts()
        self.fields['account'].queryset = CashAccount.objects.filter(is_active=True).order_by('name')
        self.fields['account'].empty_label = None
        if not self.initial.get('movement_date'):
            self.initial['movement_date'] = timezone.localdate()

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        movement_type = cleaned_data.get('movement_type')
        account = cleaned_data.get('account')

        if amount and amount <= 0:
            self.add_error('amount', 'El monto debe ser un valor positivo mayor a cero.')

        if account and amount and movement_type in [CashMovement.MovementType.EXPENSE, CashMovement.MovementType.WITHDRAWAL]:
            bal = account.get_current_balance()
            if amount > bal:
                self.add_error(
                    'amount',
                    f"Fondos insuficientes en '{account.name}'. Saldo actual: $ {bal:,.2f} COP."
                )
        return cleaned_data


class CashTransferForm(forms.Form):
    """
    Form to transfer money between financial pockets (e.g. from Nequi to Nu or Efectivo).
    """
    source_account = forms.ModelChoiceField(
        queryset=CashAccount.objects.none(),
        label="Cuenta de Origen",
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    target_account = forms.ModelChoiceField(
        queryset=CashAccount.objects.none(),
        label="Cuenta de Destino",
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=1.00,
        label="Monto a Transferir (COP)",
        widget=forms.NumberInput(attrs={
            'class': 'w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            'placeholder': '0.00',
            'step': '100',
        })
    )
    transfer_date = forms.DateField(
        label="Fecha de la Transferencia",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    notes = forms.CharField(
        required=False,
        label="Observaciones (opcional)",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            'placeholder': 'Ej. Retiro para caja chica, recarga Nequi...',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CashAccount.ensure_default_accounts()
        qs = CashAccount.objects.filter(is_active=True).order_by('name')
        self.fields['source_account'].queryset = qs
        self.fields['target_account'].queryset = qs
        self.fields['source_account'].empty_label = None
        self.fields['target_account'].empty_label = None
        if not self.initial.get('transfer_date'):
            self.initial['transfer_date'] = timezone.localdate()

    def clean(self):
        cleaned_data = super().clean()
        src = cleaned_data.get('source_account')
        tgt = cleaned_data.get('target_account')
        amount = cleaned_data.get('amount')

        if src and tgt and src.id == tgt.id:
            self.add_error('target_account', 'La cuenta de destino debe ser diferente a la de origen.')

        if src and amount:
            bal = src.get_current_balance()
            if amount > bal:
                self.add_error(
                    'amount',
                    f"Saldo insuficiente en '{src.name}' ($ {bal:,.2f} COP) para transferir $ {amount:,.2f} COP."
                )
        return cleaned_data


class CashReconciliationForm(forms.Form):
    """
    Form to record an account reconciliation / cash audit (Arqueo).
    """
    account = forms.ModelChoiceField(
        queryset=CashAccount.objects.none(),
        label="Cuenta a Conciliar / Arquear",
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    physical_balance = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0.00,
        label="Saldo Real Contado / En App (COP)",
        widget=forms.NumberInput(attrs={
            'class': 'w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            'placeholder': '0.00',
            'step': '100',
        })
    )
    notes = forms.CharField(
        required=False,
        label="Observaciones del arqueo",
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            'rows': 2,
            'placeholder': 'Detalles del arqueo, denominaciones contadas o justificación de descuadre...',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CashAccount.ensure_default_accounts()
        self.fields['account'].queryset = CashAccount.objects.filter(is_active=True).order_by('name')
        self.fields['account'].empty_label = None


class CashAccountForm(forms.ModelForm):
    """Form to create or edit a financial pocket/account."""
    COLOR_CHOICES = [
        ('emerald', 'Verde Esmeralda (Efectivo)'),
        ('purple', 'Púrpura (Nequi)'),
        ('fuchsia', 'Violeta / Fucsia (Cuenta Nu)'),
        ('amber', 'Amarillo / Ámbar (Bancolombia)'),
        ('rose', 'Rojo (Daviplata)'),
        ('blue', 'Azul Corporativo'),
    ]

    color = forms.ChoiceField(
        choices=COLOR_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )

    class Meta:
        model = CashAccount
        fields = ['name', 'account_type', 'account_number', 'initial_balance', 'color', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': 'Ej. Cuenta Nu, Nequi Principal, Billetera...',
            }),
            'account_type': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': 'Ej. Celular 3001234567 o últimos 4 dígitos',
            }),
            'initial_balance': forms.NumberInput(attrs={
                'class': 'w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'placeholder': '0.00',
                'step': '100',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
                'rows': 2,
                'placeholder': 'Notas u observaciones...',
            }),
        }


class CashFilterForm(forms.Form):
    """Filter form for the cashbook ledger."""
    account = forms.ModelChoiceField(
        queryset=CashAccount.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    movement_type = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los conceptos')] + CashMovement.MovementType.choices,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
        })
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar por concepto, préstamo o recibo...',
            'class': 'w-full pl-9 pr-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white transition',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CashAccount.ensure_default_accounts()
        self.fields['account'].queryset = CashAccount.objects.filter(is_active=True).order_by('name')
        self.fields['account'].empty_label = 'Todas las cuentas / bolsillos'
