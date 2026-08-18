from django.urls import path
from . import views

urlpatterns = [
    path('', views.payroll_dashboard, name='payroll_dashboard'),
    path('export-pdf/', views.export_payroll_pdf, name='payroll_export_pdf'),
]
