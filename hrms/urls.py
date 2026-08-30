from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import CustomLoginView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', CustomLoginView.as_view(), name='home'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('accounts/login/', CustomLoginView.as_view(), name='accounts_login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('dashboard/', include('dashboard.urls')),
    path('departments/', include('departments.urls')),
    path('employees/', include('employees.urls')),
    path('leaves/', include('leaves.urls')),
    path('payroll/', include('payroll.urls')),
    path('performance/', include('performance.urls')),
    path('reports/', include('reports.urls')),
    path('core/', include('core.urls')),
    
    # مسارات الواجهات الديناميكية
    path('settings/', TemplateView.as_view(template_name='accounts/settings.html'), name='user_settings'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)