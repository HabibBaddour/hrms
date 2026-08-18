from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from employees.models import Employee
from departments.models import Department, Position
from leaves.models import LeaveRequest  # اضبط اسم الموديل بحسب مشروعك
from core.models import InternalMessage


ROLE_OPTIONS = ['Employee', 'Manager', 'HR Admin']


def split_filter_values(raw_values):
    """Split repeated and comma-separated values into clean entries."""
    values = []
    if not raw_values:
        return values

    if isinstance(raw_values, str):
        raw_values = [raw_values]

    for raw_value in raw_values:
        if raw_value is None:
            continue
        for item in str(raw_value).split(','):
            cleaned = item.strip()
            if cleaned:
                values.append(cleaned)

    return list(dict.fromkeys(values))


def normalize_role_filters(raw_roles):
    """Normalize role filters from request lists/CSV values."""
    return split_filter_values(raw_roles)

@login_required(login_url='login')
def dashboard_redirect(request):
    """
    Central dashboard redirect view that routes users to their role-specific dashboard
    based strictly on their Employee.position.role.
    """
    user = request.user
    
    try:
        employee_profile = user.employee_profile
        position = employee_profile.position if employee_profile else None
        position_role = position.role if position else None
    except:
        employee_profile = None
        position = None
        position_role = None
    
    # Strict role-based routing based on Employee.position.role
    # SuperUser, is_staff, OR HR Admin role -> HR Dashboard
    if user.is_superuser or user.is_staff or (position_role and position_role.lower() == 'hr admin'):
        return redirect('hr_dashboard')
    
    # Manager role -> Manager Dashboard  
    elif position_role and position_role.lower() == 'manager':
        return redirect('manager_dashboard')
    
    # ALL other roles (Employee, etc.) -> Employee Dashboard
    else:
        return redirect('employee_dashboard')

@login_required(login_url='login')
def hr_dashboard(request):
    """HR Admin / SuperUser Dashboard with full administrative rights"""
    total_employees = Employee.objects.count()
    total_departments = Department.objects.count()
    total_positions = Position.objects.count()
    
    # Get pending leaves count
    try:
        pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
    except Exception:
        pending_leaves = 0
    
    context = {
        'employee_count': total_employees,
        'department_count': total_departments,
        'position_count': total_positions,
        'pending_leaves': pending_leaves,
    }
    return render(request, 'dashboard/hr_dashboard.html', context)

@login_required(login_url='login')
def manager_dashboard(request):
    """Manager Dashboard with team management capabilities"""
    # Get manager's department employees
    try:
        employee_profile = request.user.employee_profile
        if employee_profile and employee_profile.department:
            team_employees = Employee.objects.filter(department=employee_profile.department).count()
        else:
            team_employees = 0
    except:
        team_employees = 0
    
    try:
        pending_leaves = LeaveRequest.objects.filter(status='PENDING').count() if hasattr(LeaveRequest, 'objects') else 0
    except:
        pending_leaves = 0
    
    context = {
        'team_count': team_employees,
        'pending_leaves': pending_leaves,
    }
    return render(request, 'dashboard/manager_dashboard.html', context)

@login_required(login_url='login')
def employee_dashboard(request):
    """Employee Dashboard with personal features"""
    employee_profile = getattr(request.user, 'employee_profile', None)

    pending_leaves = 0
    leave_balance = 0
    last_payroll = None
    recent_leaves = []

    if employee_profile:
        pending_leaves = LeaveRequest.objects.filter(employee=employee_profile, status='PENDING').count()
        leave_balance = employee_profile.get_annual_leave_balance()
        recent_leaves = LeaveRequest.objects.filter(employee=employee_profile).order_by('-created_at')[:5]

        try:
            last_payroll = employee_profile.payrolls.order_by('-year', '-month').first()
        except Exception:
            last_payroll = None

    context = {
        'pending_leaves': pending_leaves,
        'leave_balance': leave_balance,
        'recent_leaves': recent_leaves,
        'last_payroll': last_payroll,
        'employee_profile': employee_profile,
    }
    return render(request, 'dashboard/employee_portal.html', context)

@login_required(login_url='login')
def dashboard_index(request):
    # بيانات ديناميكية حقيقية من قاعدة البيانات
    total_employees = Employee.objects.count() if hasattr(Employee, 'objects') else 0
    total_departments = Department.objects.count() if hasattr(Department, 'objects') else 0
    
    # الطلبات المعلقة للـ HR/Manager أو طلبات الموظف نفسه
    if request.user.groups.filter(name='HR').exists() or request.user.is_superuser:
        pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
        recent_leaves = LeaveRequest.objects.all().order_by('-created_at')[:5]
    else:
        pending_leaves = LeaveRequest.objects.filter(employee__user=request.user, status='PENDING').count()
        recent_leaves = LeaveRequest.objects.filter(employee__user=request.user).order_by('-created_at')[:5]

    context = {
        'total_employees': total_employees,
        'total_departments': total_departments,
        'pending_leaves': pending_leaves,
        'recent_leaves': recent_leaves,
    }
    return render(request, 'dashboard/index.html', context)     


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# قم باستيراد موديل الإشعارات والرسائل الخاص بك
# from .models import Notification, Message

@login_required
def notification_list_view(request):
    # جلب الإشعارات الخاصة بالمستخدم الحالي فقط من قاعدة البيانات
    # notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'notifications': [],  # استبدل القائمة الفارغة بـ notifications عند ربط الموديل
    }
    return render(request, 'notifications/notification_list.html', context)

@login_required
def message_list_view(request):
    """عرض قائمة الرسائل الداخلية"""
    # جلب الرسائل الخاصة بالمستخدم الحالي
    received_messages = InternalMessage.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = InternalMessage.objects.filter(sender=request.user).order_by('-created_at')
    
    # دمج الرسائل وترتيبها
    all_messages = (received_messages | sent_messages).distinct().order_by('-created_at')
    
    # جلب الأقسام للـ modal
    departments = Department.objects.all()
    
    context = {
        'messages_list': all_messages,
        'unread_count': InternalMessage.get_unread_count(request.user),
        'departments': departments,
    }
    return render(request, 'messages/message_list.html', context)


@login_required
def message_compose(request):
    """إنشاء رسالة جديدة - Gmail-style compose modal with dynamic department/user filtering"""
    if request.method == 'POST':
        recipient_filter = request.POST.get('recipient_filter')
        department_ids = split_filter_values(request.POST.getlist('department_ids'))
        role_filters = normalize_role_filters(request.POST.getlist('role_filters'))
        selected_user_ids = request.POST.getlist('selected_users')
        subject = request.POST.get('subject')
        body = request.POST.get('body')

        # تحديد المستلمين بناءً على الفلتر المختار
        recipients = []

        if recipient_filter == 'all_users':
            # جميع المستخدمين النشطين
            recipients = User.objects.filter(is_active=True).exclude(id=request.user.id)

        elif recipient_filter == 'specific_departments_users':
            # أقسام وموظفين محددين
            if selected_user_ids:
                recipients = User.objects.filter(
                    id__in=selected_user_ids,
                    is_active=True
                ).exclude(id=request.user.id)
            elif department_ids:
                recipients_qs = User.objects.filter(
                    employee_profile__position__department_id__in=department_ids,
                    is_active=True
                ).exclude(id=request.user.id)

                if role_filters:
                    recipients_qs = recipients_qs.filter(employee_profile__position__role__in=role_filters)

                recipients = recipients_qs
        
        # إنشاء الرسائل للمستلمين باستخدام bulk_create
        if recipients and subject and body:
            # Create messages in bulk for efficiency
            messages_to_create = []
            for recipient in recipients:
                messages_to_create.append(
                    InternalMessage(
                        sender=request.user,
                        recipient=recipient,
                        subject=subject,
                        body=body
                    )
                )
            
            # Bulk create messages
            messages_created = InternalMessage.objects.bulk_create(messages_to_create)
            
            # إنشاء إشعار للمستلمين
            from core.models import SystemNotification
            notifications_to_create = []
            for recipient in recipients:
                notifications_to_create.append(
                    SystemNotification(
                        recipient=recipient,
                        actor=request.user,
                        verb='submitted',
                        notification_type='SYSTEM',
                        message=f'رسالة جديدة من {request.user.username}: {subject}'
                    )
                )
            
            # Bulk create notifications
            SystemNotification.objects.bulk_create(notifications_to_create)
            
            messages.success(request, f'تم إرسال الرسالة إلى {len(messages_created)} مستخدم بنجاح')
            return redirect('message_list')
        else:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة وتحديد مستلمين صالحين')
    
    # GET request - إرجاع بيانات للـ modal
    departments = Department.objects.all()
    
    context = {
        'departments': departments,
    }
    return render(request, 'messages/message_compose.html', context)


@login_required
def get_department_users(request):
    """AJAX endpoint to get users by department IDs and optional role filter."""
    department_ids = split_filter_values(request.GET.getlist('department_ids'))
    role_filters = normalize_role_filters(request.GET.getlist('roles'))

    if not department_ids:
        return JsonResponse({'users': []})

    try:
        employees = Employee.objects.filter(
            position__department_id__in=department_ids,
            user__is_active=True
        ).select_related('user', 'position', 'department')

        if role_filters:
            employees = employees.filter(position__role__in=role_filters)

        users_data = []
        for employee in employees:
            users_data.append({
                'id': employee.user.id,
                'full_name': employee.get_full_name(),
                'role': employee.position.role if employee.position else 'N/A',
                'department_name': employee.department.name if employee.department else 'N/A',
                'position_title': employee.position.title if employee.position else 'N/A'
            })

        return JsonResponse({'users': users_data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def message_detail(request, message_id):
    """عرض تفاصيل رسالة محددة"""
    message = get_object_or_404(InternalMessage, id=message_id)
    
    # تحديد الرسالة كمقروءة إذا كان المستخدم هو المستلم
    if message.recipient == request.user and not message.is_read:
        message.mark_as_read()
    
    context = {
        'message': message,
    }
    return render(request, 'messages/message_detail.html', context)


@login_required
def message_delete(request, message_id):
    """حذف رسالة"""
    message = get_object_or_404(InternalMessage, id=message_id)
    
    # يمكن للمستخدم حذف الرسائل المرسلة أو المستلمة
    if message.sender == request.user or message.recipient == request.user:
        message.delete()
        messages.success(request, 'تم حذف الرسالة بنجاح')
    else:
        messages.error(request, 'ليس لديك صلاحية حذف هذه الرسالة')
    
    return redirect('message_list')