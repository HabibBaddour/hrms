from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.leave_list, name='leave_list'),
    path('apply/', views.apply_leave, name='apply_leave'),
    path('analyze-ai/', views.analyze_leave_ai, name='analyze_leave_ai'),
    path('<int:leave_id>/', views.leave_detail_view, name='leave_detail'),
    path('<int:leave_id>/delete/', views.leave_delete_view, name='leave_delete'),
    path('<int:pk>/approve/', views.approve_leave, name='approve_leave'),
    path('<int:pk>/reject/', views.reject_leave, name='reject_leave'),
]