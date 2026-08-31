from django.urls import path
from .views import attendance_list_view

app_name = 'attendance'

urlpatterns = [
    path('', attendance_list_view, name='attendance_list'),
]
