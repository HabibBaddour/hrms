from django.contrib import admin
from .models import Payroll

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'basic_salary', 'allowances', 'net_salary')
    list_filter = ('year', 'month')
    search_fields = ('employee__user__first_name', 'employee__emp_code')