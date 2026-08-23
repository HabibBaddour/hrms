# employees/forms.py
from django import forms
from .models import Employee, Contract
from django.contrib.auth.models import User
from departments.models import Department, Position


class EmployeeOnboardingForm(forms.ModelForm):
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    contract_type = forms.ChoiceField(label="نوع العقد", choices=Contract.CONTRACT_TYPES, required=True)
    salary = forms.DecimalField(label="الراتب الأساسي", max_digits=10, decimal_places=2, required=True)
    hire_date = forms.DateField(label="تاريخ البدء", widget=forms.DateInput(attrs={'type': 'date'}), required=True)

    class Meta:
        model = Employee
        fields = [
            'first_name', 'last_name', 'gender', 'national_id', 'birth_date',
            'phone', 'email', 'department', 'position', 'contract_type',
            'hire_date', 'salary', 'iban', 'emergency_contact',
            'emergency_contact_phone',
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select,
        }


    def clean_national_id(self):
        value = self.cleaned_data.get('national_id')
        return value or None

class EmployeeEditForm(forms.ModelForm):
    first_name = forms.CharField(label="الاسم الأول", max_length=100, required=True)
    last_name = forms.CharField(label="الاسم الأخير", max_length=100, required=True)
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    
    # Contract fields
    contract_type = forms.ChoiceField(
        label="نوع العقد",
        choices=Contract.CONTRACT_TYPES,
        required=True
    )
    salary = forms.DecimalField(
        label="الراتب الأساسي",
        max_digits=10,
        decimal_places=2,
        required=True
    )
    start_date = forms.DateField(
        label="تاريخ المباشرة",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )

    class Meta:
        model = Employee
        fields = [
            'national_id', 'phone', 'department', 'position'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
        self.fields['contract_type'].widget.attrs['class'] = 'form-select'
        # تعبئة الحقول القادمة من كائن User تلقائياً عند فتح النموذج
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        
        # تعبئة الحقول القادمة من العقد
        if self.instance:
            try:
                contract = Contract.objects.filter(employee=self.instance).first()
                if contract:
                    self.fields['contract_type'].initial = contract.contract_type
                    self.fields['salary'].initial = contract.salary
                    self.fields['start_date'].initial = contract.start_date
            except Exception:
                pass

    def save(self, commit=True):
        employee = super().save(commit=False)
        
        # حفظ التعديلات في كائن User المرتبط
        if employee.user:
            employee.user.first_name = self.cleaned_data['first_name']
            employee.user.last_name = self.cleaned_data['last_name']
            if self.cleaned_data.get('email'):
                employee.user.email = self.cleaned_data['email']
            if commit:
                employee.user.save()
        
        # تحديث أو إنشاء العقد
        contract_data = {
            'contract_type': self.cleaned_data['contract_type'],
            'salary': self.cleaned_data['salary'],
            'start_date': self.cleaned_data['start_date']
        }
        
        try:
            contract = Contract.objects.filter(employee=employee).first()
            if contract:
                for field, value in contract_data.items():
                    setattr(contract, field, value)
                if commit:
                    contract.save()
            else:
                Contract.objects.create(employee=employee, **contract_data)
        except Exception:
            Contract.objects.create(employee=employee, **contract_data)
        
        if commit:
            employee.save()
        return employee


class ContractLifecycleForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = (
            'contract_type', 'salary', 'start_date', 'end_date', 'status',
            'document', 'termination_date', 'termination_reason', 'clearance_status',
        )
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'termination_date': forms.DateInput(attrs={'type': 'date'}),
            'termination_reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
        self.fields['contract_type'].widget.attrs['class'] = 'form-select'
        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['clearance_status'].widget.attrs['class'] = 'form-select'

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'يجب أن يكون تاريخ الانتهاء بعد تاريخ البداية.')
        status = cleaned_data.get('status')
        if status in {'TERMINATED', 'RESIGNED'} and not cleaned_data.get('termination_date'):
            self.add_error('termination_date', 'أدخل تاريخ الإنهاء أو الاستقالة.')
        return cleaned_data