from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import SystemNotification


@login_required
def notification_list(request):
    """عرض جميع الإشعارات للمستخدم الحالي"""
    base_notifications = SystemNotification.objects.filter(
        recipient=request.user
    ).select_related('actor').order_by('-created_at')

    notification_type = request.GET.get('type', '')
    read_status = request.GET.get('read', '')
    importance = request.GET.get('importance', '')
    period = request.GET.get('period', '')
    search = request.GET.get('q', '').strip()

    notifications = base_notifications
    if notification_type in dict(SystemNotification.NOTIFICATION_TYPES):
        notifications = notifications.filter(notification_type=notification_type)
    if read_status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_status == 'read':
        notifications = notifications.filter(is_read=True)
    if importance == 'high':
        notifications = notifications.filter(
            Q(notification_type__in=['LEAVE', 'PAYROLL']) | Q(is_read=False)
        )
    elif importance == 'normal':
        notifications = notifications.filter(
            notification_type__in=['EMPLOYEE', 'DEPARTMENT']
        ).filter(is_read=True)
    elif importance == 'low':
        notifications = notifications.filter(notification_type='SYSTEM', is_read=True)
    if period in {'today', 'week', 'month'}:
        days = {'today': 1, 'week': 7, 'month': 30}[period]
        notifications = notifications.filter(
            created_at__gte=timezone.now() - timedelta(days=days)
        )
    if search:
        notifications = notifications.filter(
            Q(message__icontains=search)
            | Q(actor__first_name__icontains=search)
            | Q(actor__last_name__icontains=search)
            | Q(actor__username__icontains=search)
        )

    for notification in notifications:
        if notification.notification_type in {'LEAVE', 'PAYROLL'} or not notification.is_read:
            notification.importance_level = 'high'
            notification.importance_label = 'مهمة'
        elif notification.notification_type in {'EMPLOYEE', 'DEPARTMENT'}:
            notification.importance_level = 'normal'
            notification.importance_label = 'عادية'
        else:
            notification.importance_level = 'low'
            notification.importance_label = 'منخفضة'

    context = {
        'notifications': notifications,
        'total_count': base_notifications.count(),
        'unread_count': base_notifications.filter(is_read=False).count(),
        'filtered_count': notifications.count(),
        'filter_values': {
            'type': notification_type,
            'read': read_status,
            'importance': importance,
            'period': period,
            'q': search,
        },
    }
    
    return render(request, 'core/notification_list.html', context)


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """تحديد إشعار كمقروء"""
    notification = SystemNotification.objects.get(id=notification_id, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('core:notification_list')


@login_required
@require_POST
def mark_all_read(request):
    """تحديد جميع الإشعارات كمقروءة"""
    SystemNotification.mark_all_as_read(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('core:notification_list')
