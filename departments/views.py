from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from .models import Department, Position
from core.notification_utils import (
    notify_department_created, 
    notify_position_created,
    notify_department_updated,
    notify_department_deleted
)
from employees.models import Employee

@login_required
def department_list(request):
    from django.db.models import Count
    departments = Department.objects.annotate(employee_count=Count('employee'))
    return render(request, 'departments/department_list.html', {'departments': departments})

@login_required
def add_department(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description')
        
        if name and code:
            department = Department.objects.create(name=name, code=code, description=description)
            notify_department_created(department, actor=request.user)
            print(f"DEBUG: Created department {department.name} and sent notification")
            return redirect('departments:department_list')
    
    return render(request, 'departments/add_department.html')

@login_required
def department_detail(request, dept_id):
    from django.db.models import Count
    department = get_object_or_404(Department.objects.annotate(employee_count=Count('employee')), pk=dept_id)
    groups = Group.objects.all()
    
    if request.method == 'POST' and 'add_position_direct' in request.POST:
        title = request.POST.get('title')
        group_id = request.POST.get('group')
        
        if title:
            position = Position.objects.create(
                title=title,
                department=department,
                group_id=group_id if group_id else None
            )
            notify_position_created(position, actor=request.user)
            return redirect('departments:department_detail', dept_id=department.id)

    positions = department.positions.all()
    
    return render(request, 'departments/department_detail.html', {
        'department': department,
        'positions': positions,
        'groups': groups
    })

@login_required
def add_position(request):
    """الدالة التي يطلبها urls.py لتجنب AttributeError"""
    if request.method == 'POST':
        title = request.POST.get('title')
        department_id = request.POST.get('department')
        group_id = request.POST.get('group')

        if title and department_id:
            department = get_object_or_404(Department, id=department_id)
            position = Position.objects.create(
                title=title,
                department=department,
                group_id=group_id if group_id else None
            )
            notify_position_created(position, actor=request.user)
            return redirect('departments:department_detail', dept_id=department.id)

    departments = Department.objects.all()
    groups = Group.objects.all()
    return render(request, 'departments/add_position.html', {
        'departments': departments,
        'groups': groups
    })

@login_required
def edit_department(request, dept_id):
    department = get_object_or_404(Department, pk=dept_id)
    if request.method == 'POST':
        department.name = request.POST.get('name', department.name)
        department.code = request.POST.get('code', department.code)
        department.description = request.POST.get('description', department.description)
        department.save()
        notify_department_updated(department, actor=request.user)
        return redirect('departments:department_detail', dept_id=department.id)
    return render(request, 'departments/edit_department.html', {'department': department})

@login_required
def department_delete(request, dept_id):
    """Delete a department with safety checks"""
    department = get_object_or_404(Department, pk=dept_id)
    
    # Check if department has active employees or positions
    has_employees = Employee.objects.filter(department=department).exists()
    has_positions = department.positions.exists()
    
    if request.method == 'POST':
        if has_employees or has_positions:
            # Cannot delete - show error
            from django.contrib import messages
            if has_employees:
                messages.error(request, 'لا يمكن حذف القسم لوجود موظفين نشطين فيه. يرجى نقل الموظفين أولاً.')
            else:
                messages.error(request, 'لا يمكن حذف القسم لوجود مسميات وظيفية مرتبطة.')
            return redirect('departments:department_detail', dept_id=department.id)
        
        # Delete the department
        department_name = department.name  # Store name before deletion
        department.delete()
        
        # Create notification for HR users
        notify_department_deleted(department_name, actor=request.user)
        
        from django.contrib import messages
        messages.success(request, f'تم حذف القسم "{department_name}" بنجاح')
        return redirect('departments:department_list')
    
    # GET request - show confirmation
    return render(request, 'departments/department_delete.html', {
        'department': department,
        'has_employees': has_employees,
        'has_positions': has_positions
    })