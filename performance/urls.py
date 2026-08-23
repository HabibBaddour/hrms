from django.urls import path
from . import views

urlpatterns = [
    path('', views.performance_dashboard, name='performance_dashboard'),
    path('', views.performance_dashboard, name='performance_list'),
    path('add/', views.add_evaluation, name='add_evaluation'),
    path('team/', views.team_performance, name='team_performance'),
    path('campaign/<int:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('<int:pk>/', views.evaluation_detail, name='evaluation_detail'),
]
