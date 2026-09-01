from django.contrib import admin
from .models import PerformanceEvaluation, PerformanceQuestion, QuestionCategory


class PerformanceQuestionInline(admin.TabularInline):
    model = PerformanceQuestion
    extra = 0
    fields = ('category', 'text', 'max_score', 'order', 'rating')


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'evaluator', 'evaluation_type', 'period', 'overall_score', 'evaluation_date')
    list_filter = ('period', 'evaluation_type')
    search_fields = ('employee__user__first_name', 'evaluator__user__first_name')
    inlines = [PerformanceQuestionInline]


@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'order')
    ordering = ('order', 'pk')