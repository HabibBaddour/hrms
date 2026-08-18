from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import SystemNotification


@login_required
def notification_list(request):
    """عرض جميع الإشعارات للمستخدم الحالي"""
    notifications = SystemNotification.objects.filter(
        recipient=request.user
    ).select_related('actor').order_by('-created_at')
    
    print(f"DEBUG: User {request.user.username} has {notifications.count()} notifications")
    
    return render(request, 'core/notification_list.html', {
        'notifications': notifications
    })


@login_required
@csrf_exempt
def mark_notification_read(request, notification_id):
    """تحديد إشعار كمقروء"""
    notification = SystemNotification.objects.get(id=notification_id, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('core:notification_list')


@login_required
@csrf_exempt
def mark_all_read(request):
    """تحديد جميع الإشعارات كمقروءة"""
    SystemNotification.mark_all_as_read(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('core:notification_list')
