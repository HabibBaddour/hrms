from django.contrib import admin
from .models import LeaveRequest

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status', 'total_days')
    list_filter = ('status', 'leave_type', 'created_at')
    search_fields = ('employee__user__first_name', 'employee__user__last_name')