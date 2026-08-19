from django import forms

from employees.models import Employee
from .models import PerformanceEvaluation


class PerformanceEvaluationForm(forms.ModelForm):
    class Meta:
        model = PerformanceEvaluation
        fields = (
            'employee', 'period', 'period_type', 'work_quality',
            'commitment', 'cooperation', 'feedback', 'status',
        )
        widgets = {
            'feedback': forms.Textarea(attrs={'rows': 4}),
            'work_quality': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'commitment': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'cooperation': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.select_related(
            'user', 'department', 'position'
        ).order_by('user__first_name', 'user__last_name')

    def clean(self):
        cleaned_data = super().clean()
        for field in ('work_quality', 'commitment', 'cooperation'):
            value = cleaned_data.get(field)
            if value is not None and not 1 <= value <= 5:
                self.add_error(field, 'يجب أن تكون الدرجة بين 1 و5.')
        return cleaned_data
