from django.urls import path
from . import views

urlpatterns = [
    path('', views.payroll_dashboard, name='payroll_dashboard'),
    path('add/', views.create_payroll, name='create_payroll'),
    path('<int:pk>/payslip/', views.payroll_payslip, name='payroll_payslip'),
    path('my-payslips/', views.my_payslips, name='my_payslips'),
    path('export-pdf/', views.export_payroll_pdf, name='payroll_export_pdf'),
]
