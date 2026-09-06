from django import forms

from employees.models import Employee
from .models import Payroll


MONTH_CHOICES = (
    (1, 'يناير'), (2, 'فبراير'), (3, 'مارس'), (4, 'أبريل'),
    (5, 'مايو'), (6, 'يونيو'), (7, 'يوليو'), (8, 'أغسطس'),
    (9, 'سبتمبر'), (10, 'أكتوبر'), (11, 'نوفمبر'), (12, 'ديسمبر'),
)


class PayrollForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.select_related(
            'user', 'department', 'position', 'contract'
        ).filter(user__is_active=True).order_by('user__first_name', 'user__last_name')
        self.fields['employee'].widget.attrs['class'] = 'form-select'
        self.fields['employee'].widget.attrs['id'] = 'employeeSelect'
        for field_name, field in self.fields.items():
            if field_name == 'employee':
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control form-control-sm bg-dark text-light border-secondary'
            field.widget.attrs['data-calc'] = field_name

    class Meta:
        model = Payroll
        fields = (
            'employee', 'month', 'year', 'basic_salary', 'allowances',
            'bonuses', 'overtime_pay', 'deductions_absence', 'deductions_delay',
            'insurance', 'other_deductions', 'payment_method', 'bank_name',
            'account_number',
        )
        widgets = {
            'month': forms.Select(choices=MONTH_CHOICES),
            'year': forms.NumberInput(attrs={'min': 2000, 'max': 2200}),
            'payment_method': forms.Select(),
        }

    def clean(self):
        cleaned_data = super().clean()
        for field in self.fields:
            if field in ('employee', 'month', 'year', 'payment_method', 'bank_name', 'account_number'):
                continue
            value = cleaned_data.get(field)
            if value is not None and value < 0:
                self.add_error(field, 'لا يمكن أن تكون القيمة سالبة.')
        return cleaned_data