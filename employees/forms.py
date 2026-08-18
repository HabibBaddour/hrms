# employees/forms.py
from django import forms
from .models import Employee, Contract
from django.contrib.auth.models import User
from departments.models import Department, Position

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