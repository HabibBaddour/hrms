from django import forms

from employees.models import Employee
from .models import Payroll


class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = (
            'employee', 'month', 'year', 'basic_salary', 'allowances',
            'bonuses', 'deductions_absence', 'deductions_delay',
            'insurance', 'other_deductions',
        )
        widgets = {
            'month': forms.NumberInput(attrs={'min': 1, 'max': 12}),
            'year': forms.NumberInput(attrs={'min': 2000, 'max': 2200}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.select_related(
            'user', 'department', 'position', 'contract'
        ).filter(user__is_active=True).order_by('user__first_name', 'user__last_name')

    def clean(self):
        cleaned_data = super().clean()
        for field in self.fields:
            if field not in ('employee', 'month', 'year') and cleaned_data.get(field) is not None and cleaned_data[field] < 0:
                self.add_error(field, 'لا يمكن أن تكون القيمة سالبة.')
        return cleaned_data
