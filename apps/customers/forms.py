import re
from django import forms
from .models import Customer

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

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'first_name',
            'last_name',
            'document_type',
            'document_number',
            'phone',
            'whatsapp',
            'email',
            'address',
            'city',
            'status',
            'reference_name',
            'reference_relationship',
            'reference_phone',
            'notes',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. Carlos Andrés'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. Gómez Morales'}),
            'document_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'document_number': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. 1020304050'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. 3101234567'}),
            'whatsapp': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. 3101234567'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'cliente@correo.com'}),
            'address': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. Calle 45 # 12-34'}),
            'city': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. Bogotá'}),
            'status': forms.Select(attrs={'class': SELECT_CLASSES}),
            'reference_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Nombre completo de referencia'}),
            'reference_relationship': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. Hermano, Jefe, Conyugue'}),
            'reference_phone': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ej. 3209876543'}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Observaciones de solvencia, trabajo o acuerdos especiales...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['first_name'].error_messages['required'] = "El nombre del cliente es obligatorio."
        self.fields['last_name'].required = True
        self.fields['last_name'].error_messages['required'] = "El apellido del cliente es obligatorio."
        self.fields['phone'].required = True
        self.fields['phone'].error_messages['required'] = "El número de teléfono es obligatorio."
        self.fields['document_number'].required = False
        self.fields['document_type'].required = False

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if not name:
            raise forms.ValidationError("El nombre del cliente es obligatorio.")
        return name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError("El apellido del cliente es obligatorio.")
        return last_name

    def clean_document_number(self):
        doc = self.cleaned_data.get('document_number')
        if not doc or not str(doc).strip():
            return None
        doc = str(doc).strip()
        # Remove dots, dashes, spaces
        cleaned = re.sub(r'[\s\.\-]', '', doc)
        if len(cleaned) < 5:
            raise forms.ValidationError("El número de documento debe contener al menos 5 dígitos si se especifica.")
        
        # Check duplicate
        query = Customer.objects.filter(document_number__iexact=cleaned)
        if self.instance and self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise forms.ValidationError(f"Ya existe un cliente registrado con el documento {cleaned}.")
        
        return cleaned

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise forms.ValidationError("El número de teléfono es obligatorio.")
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 7:
            raise forms.ValidationError("El teléfono debe contener al menos 7 dígitos.")
        return phone


class CustomerFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-9 pr-4 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition shadow-2xs',
            'placeholder': 'Buscar cliente por nombre...',
            'hx-get': '',
            'hx-trigger': 'keyup changed delay:300ms, search',
            'hx-target': '#customer-table-container',
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Todos los estados'),
            ('ACTIVE', 'Solo Activos'),
            ('INACTIVE', 'Inactivos'),
            ('BLOCKED', 'En Mora Crítica'),
        ],
        widget=forms.Select(attrs={
            'class': 'px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition shadow-2xs',
            'hx-get': '',
            'hx-trigger': 'change',
            'hx-target': '#customer-table-container',
        })
    )

