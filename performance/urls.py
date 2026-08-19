from django.urls import path
from . import views

urlpatterns = [
    path('', views.performance_dashboard, name='performance_dashboard'),
    path('add/', views.add_evaluation, name='add_evaluation'),
    path('<int:pk>/', views.evaluation_detail, name='evaluation_detail'),
]
