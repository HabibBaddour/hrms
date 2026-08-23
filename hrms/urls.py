from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import CustomLoginView
from performance import views as performance_views
# ملاحظة: استبدل 'dashboard' باسم التطبيق الذي تحتوي فيه هذه الدوال إن كان مختلفاً
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', CustomLoginView.as_view(), name='home'),  # الصفحة الرئيسية توجيه لتسجيل الدخول
    path('login/', CustomLoginView.as_view(), name='login'),
    path('accounts/login/', CustomLoginView.as_view(), name='accounts_login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('dashboard/', include('dashboard.urls')),
    path('departments/', include('departments.urls')),
    path('employees/', include('employees.urls')),
    path('leaves/', include('leaves.urls')),
    path('payroll/', include('payroll.urls')),
    path('performance/', include('performance.urls')),
    path('evaluations/', performance_views.performance_dashboard, name='evaluations_dashboard'),
    path('evaluations/create/', performance_views.add_evaluation, name='evaluation_create'),
    path('evaluations/<int:pk>/', performance_views.evaluation_detail, name='evaluation_detail_alias'),
    path('reports/', include('reports.urls')),
    path('core/', include('core.urls')),
    
    # مسارات الواجهات الديناميكية
    path('settings/', TemplateView.as_view(template_name='accounts/settings.html'), name='user_settings'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)