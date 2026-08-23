from django import forms

from departments.models import Department
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


class EvaluationDispatchForm(forms.Form):
    """Validate the metadata and repeated questions used for bulk dispatch."""

    department_id = forms.ModelChoiceField(
        label='القسم المستهدف',
        queryset=Department.objects.none(),
        required=True,
        empty_label='اختر القسم',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_department_id'}),
    )

    title = forms.CharField(
        label='عنوان التقييم',
        max_length=200,
        required=True,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: تقييم الأداء للنصف الأول من 2026',
            'id': 'id_title',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department_id'].queryset = Department.objects.filter(
            employee__user__is_active=True,
        ).distinct().order_by('name')
        self.question_values = [
            value.strip()
            for value in self.data.getlist('questions')
        ] if self.is_bound else ['']
        self.cleaned_questions = []

    def clean(self):
        cleaned_data = super().clean()
        self.cleaned_questions = [
            value.strip()
            for value in self.data.getlist('questions')
            if value.strip()
        ] if self.is_bound else []
        if not self.cleaned_questions:
            raise forms.ValidationError('أضف سؤال تقييم واحداً على الأقل.')
        return cleaned_data
