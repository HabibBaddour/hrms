from django.urls import path
from . import views

urlpatterns = [
    path('', views.payroll_dashboard, name='payroll_dashboard'),
    path('add/', views.create_payroll, name='create_payroll'),

    path(
        'attendance-deductions/',
        views.attendance_deductions_api,
        name='payroll_attendance_deductions',
    ),

    path('<int:pk>/payslip/', views.payroll_payslip, name='payroll_payslip'),
    path('my-payslips/', views.my_payslips, name='my_payslips'),
    path('loans/apply/', views.salary_advance_apply, name='salary_advance_apply'),
    path('export-pdf/', views.export_payroll_pdf, name='payroll_export_pdf'),
]