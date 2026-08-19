from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import Employee, Contract
from .forms import ContractLifecycleForm
from departments.models import Department, Position
from core.notification_utils import notify_employee_created

@login_required
def employee_list(request):
    """عرض قائمة الموظفين مع التصفية"""
    # Extract filter parameters
    department_id = request.GET.get('department')
    contract_type = request.GET.get('contract_type')
    role = request.GET.get('role')
    search = request.GET.get('search')
    
    # Build base queryset
    try:
        employees = Employee.objects.select_related('user', 'department', 'position', 'contract').prefetch_related('user__groups').all()
    except Exception:
        employees = Employee.objects.select_related('user', 'department', 'position').prefetch_related('user__groups', 'contract').all()
    
    # Apply filters
    if department_id:
        employees = employees.filter(department_id=department_id.strip())
    
    if contract_type:
        employees = employees.filter(contract__contract_type__iexact=contract_type.strip())
    
    if role:
        employees = employees.filter(position__role__iexact=role.strip())
    
    if search:
        search = search.strip()
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Get filter options for the template
    departments = Department.objects.all()
    
    # Get contract types from Contract model choices or distinct values
    contract_types = []
    if hasattr(Contract, 'CONTRACT_TYPES'):
        contract_types = Contract.CONTRACT_TYPES
    else:
        # Fallback to distinct values from existing contracts
        contract_types = Contract.objects.values_list('contract_type', flat=True).distinct()
        contract_types = [(ct, ct) for ct in contract_types]
    
    # Get role choices from Position model
    roles = []
    if hasattr(Position, 'ROLE_CHOICES'):
        roles = Position.ROLE_CHOICES
    else:
        roles = [('Employee', 'موظف'), ('Manager', 'مدير'), ('HR Admin', 'مسؤول موارد بشرية')]
    
    context = {
        'employees': employees,
        'departments': departments,
        'contract_types': contract_types,
        'roles': roles,
    }
    
    return render(request, 'employees/employee_list.html', context)


@login_required
def get_positions_by_department(request):
    """API تُرجع المسميات الوظيفية التابعة للقسم المختار فقط مع استبعاد المشغولة"""
    department_id = request.GET.get('department_id')
    employee_id = request.GET.get('employee_id')  # For edit view
    positions = Position.objects.none()
    
    if department_id:
        if hasattr(Position, 'department'):
            # Get all positions in the department
            positions = Position.objects.filter(department_id=department_id)
            
            # Exclude positions that are already assigned to other employees
            occupied_position_ids = Employee.objects.exclude(position__isnull=True).values_list('position_id', flat=True)
            
            # If editing, include the current employee's position
            if employee_id:
                try:
                    current_employee = Employee.objects.get(id=employee_id)
                    if current_employee.position_id in occupied_position_ids:
                        occupied_position_ids = occupied_position_ids.exclude(id=current_employee.position_id)
                except Employee.DoesNotExist:
                    pass
            
            positions = positions.exclude(id__in=occupied_position_ids)
        else:
            positions = Position.objects.all()

    data = [{'id': pos.id, 'title': getattr(pos, 'title', str(pos))} for pos in positions]
    return JsonResponse(data, safe=False)


@login_required
def edit_employee(request, pk):
    """تعديل بيانات الموظف (للمستخدمين المصرح لهم فقط)"""
    if not (request.user.is_superuser or request.user.groups.filter(name='HR').exists()):
        messages.error(request, "ليس لديك صلاحية لتعديل بيانات الموظفين.")
        return redirect('employees:employee_list')
    
    employee = get_object_or_404(Employee, pk=pk)
    departments = Department.objects.all()
    
    positions = Position.objects.all()
    if employee.department and hasattr(Position, 'department'):
        positions = Position.objects.filter(department=employee.department)
    
    # جلب العقد المرتبط بالموظف
    contract = Contract.objects.filter(employee=employee).first()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. قراءة البيانات المتاحة من الـ HTML (تدعم تسميات متعددة كاحتياط)
                first_name = request.POST.get('first_name') or request.POST.get('first_name_ar') or ''
                last_name = request.POST.get('last_name') or request.POST.get('last_name_ar') or ''
                national_id = request.POST.get('national_id') or request.POST.get('national_number') or ''
                phone = request.POST.get('phone') or request.POST.get('phone_number') or ''
                
                department_id = request.POST.get('department')
                position_id = request.POST.get('position')
                
                salary = request.POST.get('salary') or request.POST.get('basic_salary')
                contract_type = request.POST.get('contract_type')
                start_date = request.POST.get('start_date') or request.POST.get('hire_date')

                # 2. تحديث كائن User المرتبط
                if employee.user:
                    employee.user.first_name = first_name.strip()
                    employee.user.last_name = last_name.strip()
                    email = request.POST.get('email')
                    if email:
                        employee.user.email = email.strip()
                    
                    # Handle password change if provided
                    new_password = request.POST.get('new_password')
                    if new_password and new_password.strip():
                        employee.user.set_password(new_password.strip())
                        employee.temporary_password = new_password.strip()
                    
                    employee.user.save()
                    employee.save()

                # 3. تحديث كائن Employee
                if hasattr(employee, 'first_name'):
                    employee.first_name = first_name.strip()
                if hasattr(employee, 'last_name'):
                    employee.last_name = last_name.strip()
                if hasattr(employee, 'national_id'):
                    employee.national_id = national_id.strip()
                # دائماً قم بتحديث حقل phone
                employee.phone = phone.strip()

                if department_id:
                    employee.department = get_object_or_404(Department, id=department_id)
                if position_id:
                    employee.position = get_object_or_404(Position, id=position_id)
                    
                    # Update user group based on new position role
                    new_position = employee.position
                    position_role = getattr(new_position, 'role', 'Employee')
                    
                    if position_role == 'HR Admin':
                        group_name = 'HR'
                    elif position_role == 'Manager':
                        group_name = 'Manager'
                    else:
                        group_name = 'Employee'
                    
                    # Clear existing groups and assign new one
                    employee.user.groups.clear()
                    group, _ = Group.objects.get_or_create(name=group_name)
                    employee.user.groups.add(group)

                employee.save()

                # 4. تحديث أو إنشاء العقد
                if salary or start_date or contract_type:
                    contract, created = Contract.objects.get_or_create(employee=employee)
                    if salary:
                        try:
                            contract.salary = float(salary)
                        except ValueError:
                            contract.salary = 0.00
                    if contract_type:
                        contract.contract_type = contract_type
                    if start_date:
                        contract.start_date = start_date
                    contract.save()

                messages.success(request, f"تم تحديث بيانات الموظف {first_name} {last_name} بنجاح!")
                return redirect('employees:employee_list')
                
        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء تحديث البيانات: {str(e)}")

    # تجهيز قيم البداية للعرض في ملف edit_employee.html
    # أولوية البيانات من User model ثم Employee model
    first_name = ''
    last_name = ''
    
    if employee.user:
        first_name = employee.user.first_name or ''
        last_name = employee.user.last_name or ''
    
    # Fallback to Employee model fields if User fields are empty
    if not first_name and hasattr(employee, 'first_name'):
        first_name = employee.first_name or ''
    if not last_name and hasattr(employee, 'last_name'):
        last_name = employee.last_name or ''
    
    phone = getattr(employee, 'phone', '') or getattr(employee, 'phone_number', '')
    national_id = getattr(employee, 'national_id', '')
    
    context = {
        'employee': employee,
        'departments': departments,
        'positions': positions,
        'contract': contract,
        'first_name': first_name,
        'last_name': last_name,
        'phone': phone,
        'national_id': national_id,
        'email': employee.user.email if employee.user else '',
        'username': employee.user.username if employee.user else '',
        'temporary_password': employee.temporary_password if employee.temporary_password else '',
    }

    return render(request, 'employees/edit_employee.html', context)


@login_required
def create_employee_wizard(request):
    """دالة تعيين الموظف عبر استمارة الخطوات وتوليد حساب له تلقائياً"""
    departments = Department.objects.all()

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        national_id = request.POST.get('national_id', '').strip() or request.POST.get('national_number', '').strip()
        phone = request.POST.get('phone', '').strip() or request.POST.get('phone_number', '').strip()
        
        department_id = request.POST.get('department')
        position_id = request.POST.get('position')
        
        salary = request.POST.get('salary') or request.POST.get('basic_salary')
        contract_type = request.POST.get('contract_type')
        start_date = request.POST.get('start_date') or request.POST.get('hire_date')

        department = get_object_or_404(Department, id=department_id)
        position = get_object_or_404(Position, id=position_id)

        # Use position.role field for email generation (only 3 roles: Manager, HR Admin, Employee)
        position_role = getattr(position, 'role', 'Employee')
        
        if position_role == 'Manager':
            group_name = 'Manager'
            role_code = 'man'
        elif position_role == 'HR Admin':
            group_name = 'HR'
            role_code = 'hr'
        else:
            group_name = 'Employee'
            role_code = 'emp'

        dept_code = (getattr(department, 'code', None) or 'gen').lower()
        email = f"{first_name.lower()}.{dept_code}.{role_code}@hrms.co"
        
        # Check for duplicate email
        if User.objects.filter(email=email).exists():
            messages.error(request, f"البريد الإلكتروني {email} مستخدم بالفعل. يرجى استخدام اسم مختلف.")
            return render(request, 'employees/create_employee_wizard.html', {'departments': departments})
        
        # Check for duplicate national_id
        if national_id and Employee.objects.filter(national_id=national_id).exists():
            messages.error(request, f"الرقم الوطني {national_id} مستخدم بالفعل.")
            return render(request, 'employees/create_employee_wizard.html', {'departments': departments})
        
        # Check for duplicate name and position
        if Employee.objects.filter(
            user__first_name__iexact=first_name,
            user__last_name__iexact=last_name,
            position=position
        ).exists():
            messages.error(request, f"الموظف {first_name} {last_name} يشغل هذا المنصب بالفعل.")
            return render(request, 'employees/create_employee_wizard.html', {'departments': departments})
        
        base_username = f"{first_name.lower()}_{dept_code}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        password = f"{first_name.capitalize()}123"

        try:
            with transaction.atomic():
                # 1. Determine user flags based on position.role (STRICT role assignment)
                is_staff = False
                is_superuser = False
                
                if position_role == 'HR Admin':
                    is_staff = True
                    is_superuser = False  # HR Admin is staff but not superuser
                elif position_role == 'Manager':
                    is_staff = False
                    is_superuser = False
                else:  # Employee or any other role
                    is_staff = False
                    is_superuser = False

                # 2. Create User with proper password hashing and role-based flags
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                    is_staff=is_staff,
                    is_superuser=is_superuser
                )

                # 3. Assign user to appropriate group based on position.role
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)

                # 4. Create Employee with all fields
                employee = Employee.objects.create(
                    user=user,
                    department=department,
                    position=position,
                    first_name=first_name,
                    last_name=last_name,
                    national_id=national_id,
                    phone=phone,
                    temporary_password=password
                )
                
                # 5. Send notification to HR users
                notify_employee_created(employee, actor=request.user)

                # 6. Create Contract with all fields (ensure all data is persisted)
                if salary and contract_type and start_date:
                    Contract.objects.create(
                        employee=employee,
                        salary=salary,
                        contract_type=contract_type,
                        start_date=start_date
                    )

            messages.success(request, f"تم إنشاء حساب الموظف {first_name} {last_name} بنجاح! اسم المستخدم: {username} - كلمة المرور: {password}")
            return redirect('employees:employee_list')

        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء التعيين: {str(e)}")

    return render(request, 'employees/create_employee_wizard.html', {
        'departments': departments,
    })


@login_required
def user_profile(request):
    """User profile page with avatar upload functionality"""
    try:
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.error(request, "No employee profile found for your account.")
        return redirect('dashboard')

    contract = None
    try:
        contract = employee.contract
    except Exception:
        pass

    if request.method == 'POST':
        if 'profile_picture' in request.FILES:
            employee.profile_picture = request.FILES['profile_picture']
            employee.save()
            messages.success(request, "تم تحديث صورة الملف الشخصي بنجاح!")
            return redirect('employees:profile')

        date_of_birth = request.POST.get('date_of_birth')
        address = (request.POST.get('address') or '').strip()
        primary_phone = (request.POST.get('primary_phone') or '').strip()

        if date_of_birth:
            employee.date_of_birth = date_of_birth

        if address:
            employee.address = address

        if primary_phone:
            employee.phone = primary_phone

        employee.save()

        employee.phone_numbers.all().delete()
        phone_values = []
        for key in sorted(request.POST.keys()):
            if key.startswith('phone_') and key != 'phone_':
                value = (request.POST.get(key) or '').strip()
                if value:
                    phone_values.append(value)

        if primary_phone:
            phone_values = [primary_phone] + [p for p in phone_values if p != primary_phone]

        seen = set()
        for index, value in enumerate(phone_values):
            if value in seen:
                continue
            seen.add(value)
            employee.phone_numbers.create(
                number=value,
                label='Mobile' if index == 0 else f'Phone {index + 1}',
                is_primary=(index == 0),
            )

        if not primary_phone and employee.phone:
            employee.phone = ''
            employee.save()

        messages.success(request, "تم تحديث بيانات الملف الشخصي بنجاح!")
        return redirect('employees:profile')

    context = {
        'employee': employee,
        'contract': contract,
        'user': request.user,
        'phone_numbers': list(employee.phone_numbers.all()) or [
            {'number': employee.phone or '', 'label': 'Mobile', 'is_primary': True}
        ],
    }
    return render(request, 'employees/profile.html', context)


@login_required(login_url='login')
def contract_detail(request, pk):
    if not (request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name__iexact='HR').exists()):
        messages.error(request, 'ليس لديك صلاحية تعديل سجلات العقود.')
        return redirect('employees:profile')
    employee = get_object_or_404(
        Employee.objects.select_related('user', 'department', 'position'), pk=pk
    )
    contract, _ = Contract.objects.get_or_create(
        employee=employee,
        defaults={'salary': 0, 'start_date': timezone.localdate()},
    )
    if request.method == 'POST':
        form = ContractLifecycleForm(request.POST, request.FILES, instance=contract)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث سجل العقد بنجاح.')
            return redirect('employees:contract_detail', pk=employee.pk)
    else:
        form = ContractLifecycleForm(instance=contract)
    return render(request, 'employees/contract_detail.html', {'employee': employee, 'contract': contract, 'form': form})


@login_required(login_url='login')
def contract_print(request, pk):
    employee = get_object_or_404(
        Employee.objects.select_related('user', 'department', 'position', 'contract'), pk=pk
    )
    is_hr = request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name__iexact='HR').exists()
    if not is_hr and employee.user_id != request.user.id:
        messages.error(request, 'لا يمكنك عرض عقد موظف آخر.')
        return redirect('employees:profile')
    contract = getattr(employee, 'contract', None)
    if not contract:
        messages.error(request, 'لا يوجد عقد مسجل لهذا الموظف.')
        return redirect('employees:profile' if not is_hr else 'employees:employee_list')
    return render(request, 'employees/contract_print.html', {
        'employee': employee,
        'contract': contract,
        'is_hr': is_hr,
    })


@login_required(login_url='login')
def offboard_employee(request, pk):
    if not (request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name__iexact='HR').exists()):
        messages.error(request, 'ليس لديك صلاحية تنفيذ إنهاء الخدمة.')
        return redirect('employees:profile')
    employee = get_object_or_404(Employee.objects.select_related('contract', 'user'), pk=pk)
    contract = get_object_or_404(Contract, employee=employee)
    if request.method == 'POST':
        contract.status = request.POST.get('status', 'TERMINATED')
        contract.termination_date = request.POST.get('termination_date') or timezone.localdate()
        contract.termination_reason = request.POST.get('termination_reason', '').strip()
        contract.clearance_status = request.POST.get('clearance_status', 'PENDING')
        contract.save(update_fields=('status', 'termination_date', 'termination_reason', 'clearance_status'))
        if employee.user:
            employee.user.is_active = False
            employee.user.save(update_fields=('is_active',))
        messages.success(request, 'تم تسجيل إجراء إنهاء الخدمة وتعطيل حساب الموظف.')
        return redirect('employees:contract_detail', pk=employee.pk)
    return render(request, 'employees/offboard_employee.html', {'employee': employee, 'contract': contract})