from django.urls import path
from . import views

app_name = 'departments'

urlpatterns = [
    path('', views.department_list, name='department_list'),
    path('add/', views.add_department, name='add_department'),
    path('positions/<int:pk>/delete/', views.delete_position, name='delete_position'),
    path('positions/<int:position_id>/', views.position_detail, name='position_detail'),
    path('<int:dept_id>/', views.department_detail, name='department_detail'),
    path('<int:dept_id>/edit/', views.edit_department, name='edit_department'),
    path('<int:dept_id>/delete/', views.department_delete, name='department_delete'),
    path('positions/add/', views.add_position, name='add_position'),
    path('positions/<int:pk>/edit/', views.edit_position, name='edit_position'),
]