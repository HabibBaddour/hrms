from django import forms

from departments.models import Department
from employees.models import Employee
from .models import PerformanceEvaluation, QuestionCategory


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
    """Validate dispatch metadata and the per-pillar (category) question groups."""

    departments = forms.ModelMultipleChoiceField(
        label='الأقسام المستهدفة',
        queryset=Department.objects.none(),
        required=True,
        error_messages={
            'required': 'اختر قسماً واحداً على الأقل أو كافة الأقسام.',
            'invalid_pk_value': 'قيمة القسم المحدد غير صالحة.',
            'invalid_list': 'اختيار الأقسام غير صالح.',
        },
        widget=forms.CheckboxSelectMultiple,
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

    evaluation_type = forms.ChoiceField(
        label='نوع التقييم / المحور الرئيسي',
        choices=PerformanceEvaluation.EVALUATION_TYPES,
        required=False,
        initial='COMPETENCIES',
        widget=forms.HiddenInput(attrs={
            'id': 'id_evaluation_type',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['departments'].queryset = Department.objects.filter(
            employee__user__is_active=True,
        ).distinct().order_by('name')
        self.categories = list(
            QuestionCategory.objects.all().order_by('order', 'pk')
        )
        self.selected_department_ids = [
            value
            for value in self.data.getlist('departments')
        ] if self.is_bound else []
        self.category_values = {
            category.code: [
                value.strip()
                for value in self.data.getlist(f'questions_{category.code}')
            ] or ['']
            for category in self.categories
        }
        if self.is_bound:
            self.question_values = [
                value.strip()
                for value in self.data.getlist('questions')
            ]
        else:
            self.question_values = ['']
        self.cleaned_questions_by_category = {}
        self.cleaned_questions = []

    def clean(self):
        cleaned_data = super().clean()
        self.cleaned_questions_by_category = {
            category.code: [
                value.strip()
                for value in self.data.getlist(f'questions_{category.code}')
                if value.strip()
            ]
            for category in self.categories
        }
        self.cleaned_questions = [
            question
            for values in self.cleaned_questions_by_category.values()
            for question in values
        ]
        if not self.cleaned_questions:
            raise forms.ValidationError('أضف سؤال تقييم واحداً على الأقل.')
        return cleaned_data
