from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('add-wizard/', views.create_employee_wizard, name='add_employee_wizard'),
    path('<int:pk>/edit/', views.edit_employee, name='edit_employee'),
    path('profile/', views.user_profile, name='profile'),
    # مسار جلب المسميات الوظيفية للقسم
    path('api/positions/', views.get_positions_by_department, name='get_positions_by_department'),
]