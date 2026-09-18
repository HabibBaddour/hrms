from django.contrib import admin
from .models import Payroll, SalaryAdvance

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'basic_salary', 'allowances', 'net_salary')
    list_filter = ('year', 'month')
    search_fields = ('employee__user__first_name', 'employee__emp_code')

@admin.register(SalaryAdvance)
class SalaryAdvanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'amount', 'months', 'monthly_deduction', 'remaining_balance', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__employee_number', 'reason')
    list_editable = ('status',)