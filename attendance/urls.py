from django.urls import path

from .views import (
    attendance_calendar_events,
    attendance_list_view,
    day_details_api,
    team_month_api,
)

app_name = 'attendance'

urlpatterns = [
    path('', attendance_list_view, name='attendance_list'),
    path('api/calendar-events/', attendance_calendar_events, name='attendance_calendar_events'),
    path('api/day-details/', day_details_api, name='day_details_api'),
    path('api/team-month/', team_month_api, name='team_month_api'),
]
