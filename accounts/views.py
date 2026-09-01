from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from django.utils import timezone

from attendance.models import AttendanceLog

class CustomLoginView(LoginView):
    """تخصيص صفحة تسجيل الدخول لدعم اسم المستخدم أو البريد الإلكتروني"""
    template_name = 'accounts/login.html'
    
    def dispatch(self, request, *args, **kwargs):
        # If user is already authenticated, redirect to appropriate dashboard
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        # محاولة تسجيل الدخول بالبريد الإلكتروني إذا لم يكن اسم المستخدم موجود
        if '@' in username:
            try:
                user = User.objects.get(email=username)
                username = user.username
            except User.DoesNotExist:
                pass
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                # تسجيل توقيت الدخول في جدول الحضور
                AttendanceLog.record_checkin(user)
                messages.success(request, f"مرحباً {user.get_full_name() or user.username}!")
                return render(request, self.template_name, {
                    'login_success': True,
                    'username': user.username,
                    'login_time': timezone.now().isoformat(),
                    'dashboard_url': self.get_success_url().url,
                })
            else:
                messages.error(request, "حسابك غير نشط. يرجى التواصل مع الإدارة.")
        else:
            messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة.")
        
        return render(request, self.template_name, {'form': self.get_form()})
    
    def get_success_url(self):
        """توجيه المستخدم بناءً على دوره بعد تسجيل الدخول"""
        # Redirect to the central dashboard redirect view which will route based on role
        return redirect('/dashboard/')


class CustomLogoutView(LogoutView):
    """تسجيل توقيت الخروج في جدول الحضور قبل إنهاء الجلسة"""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            AttendanceLog.record_checkout(request.user)
        return super().dispatch(request, *args, **kwargs)
