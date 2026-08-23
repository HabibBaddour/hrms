from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_redirect, name='dashboard'),
    path('hr/', views.hr_dashboard, name='hr_dashboard'),
    path('admin/', views.hr_dashboard, name='admin_dashboard'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('employee/', views.employee_dashboard, name='employee_dashboard'),
    path('main/', views.dashboard_index, name='dashboard_main'),
    path('messages/', views.message_list_view, name='message_list'),
    path('messages/compose/', views.message_compose, name='message_compose'),
    path('messages/<int:message_id>/', views.message_detail, name='message_detail'),
    path('messages/<int:message_id>/delete/', views.message_delete, name='message_delete'),
    path('messages/api/get-department-users/', views.get_department_users, name='get_department_users'),
]