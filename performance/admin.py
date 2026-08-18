from django.contrib import admin
from .models import PerformanceEvaluation

@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'evaluator', 'period', 'overall_score', 'evaluation_date')
    list_filter = ('period',)
    search_fields = ('employee__user__first_name', 'evaluator__user__first_name')