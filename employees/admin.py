from django.contrib import admin

from .models import Employee, Contract, Payslip, PayslipEarning, PayslipDeduction


class PayslipEarningInline(admin.TabularInline):
    model = PayslipEarning
    extra = 1
    fields = ('title', 'amount')


class PayslipDeductionInline(admin.TabularInline):
    model = PayslipDeduction
    extra = 1
    fields = ('title', 'amount')


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'net_salary', 'created_at')
    list_filter = ('year', 'month')
    search_fields = (
        'employee__user__username',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__employee_number',
    )
    autocomplete_fields = ('employee',)
    date_hierarchy = 'created_at'
    ordering = ('-year', '-month', '-id')
    inlines = (PayslipEarningInline, PayslipDeductionInline)

    def net_salary(self, obj):
        return obj.net_salary

    net_salary.short_description = 'صافي الراتب'
    net_salary.admin_order_field = 'basic_salary'


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'employee_number',
    )


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    search_fields = (
        'employee__user__username',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__employee_number',
    )