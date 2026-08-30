from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('add-wizard/', views.create_employee_wizard, name='add_employee_wizard'),
    path('<int:pk>/edit/', views.edit_employee, name='edit_employee'),
    path('<int:pk>/contract/', views.contract_detail, name='contract_detail'),
    path('<int:pk>/contract/print/', views.contract_print, name='contract_print'),
    path('<int:pk>/offboard/', views.offboard_employee, name='offboard_employee'),
    path('profile/', views.user_profile, name='profile'),
    path('payslips/', views.payslip_list_view, name='payslip_list'),
    path('payslips/<int:payslip_id>/', views.payslip_detail_view, name='payslip_detail'),
    path('payslips/<int:payslip_id>/pdf/', views.export_payslip_pdf, name='payslip_pdf'),
    # مسار جلب المسميات الوظيفية للقسم
    path('api/positions/', views.get_positions_by_department, name='get_positions_by_department'),
]