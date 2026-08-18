from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
    path('payroll/', views.payroll_report, name='payroll_report'),
    path('leaves/', views.leave_report, name='leave_report'),
    path('performance/', views.performance_report, name='performance_report'),
]
