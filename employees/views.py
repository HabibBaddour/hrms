from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.db import transaction
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.template.loader import render_to_string
from decimal import Decimal
from .models import Employee, Contract, Payslip
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
    sort_by = request.GET.get('sort_by', 'id')
    order = request.GET.get('order', 'asc')
    
    # Build base queryset
    try:
        employees = Employee.objects.select_related('user', 'department', 'position', 'contract').prefetch_related('user__groups').all()
    except Exception:
        employees = Employee.objects.select_related('user', 'department', 'position').prefetch_related('user__groups', 'contract').all()

    manager_department = None
    is_manager = request.user.groups.filter(name='Manager').exists()
    if not is_manager:
        employee_profile = getattr(request.user, 'employee_profile', None)
        position = getattr(employee_profile, 'position', None) if employee_profile else None
        if position and getattr(position, 'role', None) == 'Manager':
            is_manager = True
    if is_manager:
        employee_profile = getattr(request.user, 'employee_profile', None)
        manager_department = getattr(employee_profile, 'department', None)
        if manager_department is None and hasattr(request.user, 'department'):
            manager_department = request.user.department
        if manager_department is not None:
            employees = employees.filter(department=manager_department)
    
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

    sort_mapping = {
        'id': 'id',
        'name': 'user__first_name',
        'salary': 'contract__salary',
        'date': 'contract__start_date',
    }
    if order not in ('asc', 'desc'):
        order = 'asc'
    sort_field = sort_mapping.get(sort_by, 'id')
    employees = employees.order_by(f"{'-' if order == 'desc' else ''}{sort_field}", 'id')
    
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
        'total_employees': employees.count(),
        'departments': departments,
        'contract_types': contract_types,
        'roles': roles,
        'sort_by': sort_by if sort_by in sort_mapping else 'id',
        'order': order,
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

    data = []
    for pos in positions:
        role = getattr(pos, 'role', 'Employee')
        if role == 'Manager':
            role_code = 'man'
        elif role == 'HR Admin':
            role_code = 'hr'
        else:
            role_code = 'emp'
        data.append({
            'id': pos.id,
            'title': getattr(pos, 'title', str(pos)),
            'salary_min': float(pos.salary_min) if pos.salary_min is not None else 0,
            'salary_max': float(pos.salary_max) if pos.salary_max is not None else 0,
            'role': role,
            'role_code': role_code,
            'dept_code': (getattr(pos.department, 'code', None) or 'gen').lower(),
            'dept_id': pos.department_id,
        })
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
                employee.salary = salary if salary else None

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
        gender = request.POST.get('gender', 'male')
        birth_date = request.POST.get('birth_date') or None
        national_id = request.POST.get('national_id', '').strip() or request.POST.get('national_number', '').strip()
        phone = request.POST.get('phone', '').strip() or request.POST.get('phone_number', '').strip()
        iban = request.POST.get('iban', '').strip()
        
        department_id = request.POST.get('department')
        position_id = request.POST.get('position')
        
        salary = request.POST.get('salary') or request.POST.get('basic_salary')
        contract_type = request.POST.get('contract_type')
        start_date = request.POST.get('start_date') or request.POST.get('hire_date') or request.POST.get('contract_start_date')
        end_date = request.POST.get('contract_end_date') or request.POST.get('end_date')
        requested_email = request.POST.get('email', '').strip()

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
        email = requested_email or f"{first_name.lower()}.{dept_code}-{department.id}.{role_code}@hrms.co"
        
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
        
        base_username = f"{first_name}_{last_name}"
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
                    gender=gender,
                    birth_date=birth_date,
                    national_id=national_id,
                    phone=phone,
                    iban=iban,
                    salary=salary if salary else None,
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
                        start_date=start_date,
                        end_date=end_date or None
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
        if request.POST.get('form_name') == 'account':
            return _update_account(request)

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


def _update_account(request):
    """Handle the Account Credentials tab: update e-mail and/or change password."""
    user = request.user
    if request.POST.get('form_name') != 'account':
        return None

    email = (request.POST.get('email') or '').strip()
    current_password = request.POST.get('current_password') or ''
    new_password = request.POST.get('new_password') or ''
    confirm_password = request.POST.get('confirm_password') or ''

    if not current_password:
        messages.error(request, "أدخل كلمة السر الحالية لتأكيد هويتك.")
        return redirect('employees:profile')

    if not user.check_password(current_password):
        messages.error(request, "كلمة السر الحالية غير صحيحة. تحقق من الإدخال وأعد المحاولة.")
        return redirect('employees:profile')

    if email and email != user.email:
        user.email = email

    if new_password:
        if new_password != confirm_password:
            messages.error(request, "كلمة السر الجديدة غير مطابقة لتأكيدها.")
            return redirect('employees:profile')
        if len(new_password) < 8:
            messages.error(request, "كلمة السر الجديدة يجب أن تتكون من 8 رموز على الأقل.")
            return redirect('employees:profile')
        user.set_password(new_password)

    user.save()
    if new_password:
        update_session_auth_hash(request, user)

    messages.success(request, "تم تحديث بيانات الحساب بنجاح.")
    return redirect('employees:profile')


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


def _is_hr_user(user):
    return user.is_superuser or user.is_staff or user.groups.filter(name__iexact='HR').exists()


def _payslip_queryset():
    return Payslip.objects.select_related(
        'employee__user', 'employee__department', 'employee__position',
    ).prefetch_related('earnings', 'deductions')


def _can_view_payslip(user, payslip):
    """الموظف يرى قسيمته فقط، ومسؤولو HR يرون كل القسائم."""
    return _is_hr_user(user) or (payslip.employee.user_id and payslip.employee.user_id == user.id)


def _user_assigned_salary(user):
    """الراتب المعتمد للمستخدم: راتب الموظف → راتب المسمى الوظيفي → راتب العقد."""
    employee = getattr(user, 'employee_profile', None)
    if not employee:
        return Decimal('0.00')
    if employee.salary:
        return employee.salary
    base_salary = getattr(getattr(employee, 'position', None), 'base_salary', None)
    if base_salary:
        return base_salary
    contract_salary = getattr(getattr(employee, 'contract', None), 'salary', None)
    if contract_salary:
        return contract_salary
    return Decimal('0.00')


def _mask_iban(value):
    if not value:
        return '—'
    text = str(value).replace(' ', '')
    if len(text) <= 8:
        return f"{text[:2]} **** **** {text[-2:]}"
    return f"{text[:4]} **** **** **** {text[-4:]}"


def _sum_matching(items, keywords):
    total = Decimal('0.00')
    for item in items:
        title = (getattr(item, 'title', '') or '').lower()
        if any(keyword in title for keyword in keywords):
            total += getattr(item, 'amount', Decimal('0.00')) or Decimal('0.00')
    return total


def _group_salary_components(items, labels):
    components = []
    remaining = list(items)
    used_ids = set()

    for label, keywords, icon in labels:
        matches = [item for item in remaining if item.id not in used_ids and any(keyword in (getattr(item, 'title', '') or '').lower() for keyword in keywords)]
        if not matches:
            continue
        amount = sum((getattr(item, 'amount', Decimal('0.00')) or Decimal('0.00')) for item in matches)
        components.append({
            'label': label,
            'amount': amount,
            'icon': icon,
            'items': [{'title': getattr(m, 'title', ''), 'amount': getattr(m, 'amount', Decimal('0.00'))} for m in matches]
        })
        used_ids.update(item.id for item in matches)

    leftover_items = [item for item in remaining if item.id not in used_ids]
    if leftover_items:
        leftover = sum((getattr(item, 'amount', Decimal('0.00')) or Decimal('0.00')) for item in leftover_items)
        if leftover > 0:
            components.append({
                'label': 'مستحقات / استقطاعات أخرى',
                'amount': leftover,
                'icon': 'fa-folder-plus',
                'items': [{'title': getattr(m, 'title', ''), 'amount': getattr(m, 'amount', Decimal('0.00'))} for m in leftover_items]
            })

    return components


@login_required(login_url='login')
def payslip_list_view(request):
    """قائمة القسائم الشخصية: كل دور مسجّل يرى قسائمه المرتبطة بمسمّاه الوظيفي.

    - `payslips`: قسائم المستخدم فقط.
    - `payslips_count`: عدد القسائم.
    - `total_net_salary`: مجموع صافي القسائم، أو الراتب المعتمد كمخزون احتياطي.
    - `user_department`: اسم قسم المستخدم لبطاقة «القسم».
    """
    user = request.user
    employee = getattr(user, 'employee_profile', None)

    user_payslips = Payslip.objects.none()
    if employee is not None:
        user_payslips = Payslip.objects.filter(employee=employee).select_related(
            'employee__user', 'employee__department', 'employee__position',
        ).prefetch_related('earnings', 'deductions').order_by('-year', '-month', '-id')

    payslips_count = user_payslips.count()
    total_net_salary = sum(p.net_salary for p in user_payslips)
    if payslips_count == 0:
        total_net_salary = _user_assigned_salary(user)

    context = {
        'payslips': user_payslips,
        'payslips_count': payslips_count,
        'count': payslips_count,
        'total_net_salary': total_net_salary,
        'user_department': (
            employee.department.name if getattr(employee, 'department', None) else None
        ),
        'is_hr': _is_hr_user(user),
    }
    return render(request, 'employees/payslip_list.html', context)


@login_required(login_url='login')
def payslip_detail_view(request, payslip_id):
    """عرض قسيمة راتب ديناميكية مع تفاصيل كاملة للمستحقات والاستقطاعات."""
    payslip = get_object_or_404(_payslip_queryset(), pk=payslip_id)
    if not _can_view_payslip(request.user, payslip):
        messages.error(request, 'لا يمكنك الاطلاع على قسيمة راتب موظف آخر.')
        return redirect('employees:profile')

    employee = payslip.employee
    earning_items = list(payslip.earnings.all())
    deduction_items = list(payslip.deductions.all())

    # === SPECIFIC CATEGORY SUMMARIES ===
    bonuses_amount = _sum_matching(earning_items, ['مكافأة', 'مكافآت', 'bonus', 'incentive', 'حافز', 'حوافز'])
    allowances_amount = _sum_matching(earning_items, ['بدل', 'بدلات', 'allowance', 'housing', 'transport', 'سكن', 'مواصلات', 'انتقال', 'هاتف'])
    overtime_amount = _sum_matching(earning_items, ['إضافي', 'اضافي', 'overtime', 'extra', 'ساعة إضافية', 'ساعات إضافية'])

    discounts_amount = _sum_matching(deduction_items, ['خصم', 'خصومات', 'جزاء', 'غرامة', 'penalty', 'discount', 'deduction', 'absent', 'غياب', 'تأخير', 'انضباط'])
    insurance_amount = _sum_matching(deduction_items, ['تأمين', 'insurance', 'social', 'التأمينات', 'اجتماعي', 'gosi'])
    taxes_amount = _sum_matching(deduction_items, ['ضريبة', 'tax', 'taxes', 'الضرائب', 'دخل', 'vat'])
    loans_amount = _sum_matching(deduction_items, ['سلفة', 'سلف', 'قرض', 'loan', 'advance', 'قسط', 'installment'])

    # === EARNINGS BREAKDOWN (المستحقات) ===
    earning_components = [
        {
            'label': 'الراتب الأساسي (Basic Salary)',
            'amount': payslip.basic_salary,
            'icon': 'fa-money-bill-wave',
            'type': 'basic',
        },
    ]
    grouped_earnings = _group_salary_components(earning_items, [
        ('المكافآت والحوافز (Bonuses)', ['مكافأة', 'مكافآت', 'bonus', 'incentive', 'حافز', 'حوافز'], 'fa-gift'),
        ('البدلات الثابتة (Allowances)', ['بدل', 'بدلات', 'allowance', 'housing', 'transport', 'سكن', 'مواصلات', 'انتقال', 'هاتف'], 'fa-house-user'),
        ('أجر العمل الإضافي (Overtime Pay)', ['إضافي', 'اضافي', 'overtime', 'extra', 'ساعة إضافية', 'ساعات إضافية'], 'fa-business-time'),
    ])
    earning_components.extend(grouped_earnings)

    # === DEDUCTIONS BREAKDOWN (الاستقطاعات) ===
    deduction_components = _group_salary_components(deduction_items, [
        ('الخصومات والجزاءات (Discounts/Penalties)', ['خصم', 'خصومات', 'جزاء', 'غرامة', 'penalty', 'discount', 'deduction', 'absent', 'غياب', 'تأخير', 'انضباط'], 'fa-user-clock'),
        ('التأمينات الاجتماعية (Social Security)', ['تأمين', 'insurance', 'social', 'التأمينات', 'اجتماعي', 'gosi'], 'fa-shield-halved'),
        ('الضرائب والاستقطاعات الحكومية (Taxes)', ['ضريبة', 'tax', 'taxes', 'الضرائب', 'دخل', 'vat'], 'fa-file-invoice-dollar'),
        ('السلف وأقساط القروض (Loans & Advances)', ['سلفة', 'سلف', 'قرض', 'loan', 'advance', 'قسط', 'installment'], 'fa-hand-holding-dollar'),
    ])

    # === PAYMENT DETAILS (تفاصيل الدفع) ===
    iban_val = getattr(employee, 'iban', None)
    bank_name = getattr(employee, 'bank_name', None) or getattr(employee, 'bank', None)
    if not bank_name and iban_val:
        bank_name = 'مصرف الراجحي' if 'RJHI' in str(iban_val).upper() else ('البنك الأهلي السعودي' if 'NCBK' in str(iban_val).upper() else 'الحساب البنكي المعتمد')
    
    payment_details = {
        'bank_name': bank_name or 'صرف نقدي مباشر / عبر الخزينة',
        'iban_masked': _mask_iban(iban_val),
        'iban_raw': iban_val or '',
        'method': 'تحويل بنكي مباشر (Bank Transfer)' if iban_val else 'صرف نقدي (Cash Payment)',
    }

    # === SALARY CALCULATIONS (الحسابات المالية) ===
    basic_salary = payslip.basic_salary or Decimal('0.00')
    additional_earnings = payslip.total_earnings or Decimal('0.00')
    gross_salary = basic_salary + additional_earnings
    total_deductions = payslip.total_deductions or Decimal('0.00')
    net_salary = gross_salary - total_deductions

    context = {
        'payslip': payslip,
        'employee': employee,
        'is_hr': _is_hr_user(request.user),
        # Categorized calculations
        'basic_salary': basic_salary,
        'bonuses_amount': bonuses_amount,
        'allowances_amount': allowances_amount,
        'overtime_amount': overtime_amount,
        'discounts_amount': discounts_amount,
        'insurance_amount': insurance_amount,
        'taxes_amount': taxes_amount,
        'loans_amount': loans_amount,
        'additional_earnings': additional_earnings,
        'gross_salary': gross_salary,
        # Total calculations
        'total_earnings': gross_salary,
        'total_deductions': total_deductions,
        'net_salary': net_salary,
        # Component lists
        'earning_components': earning_components,
        'deduction_components': deduction_components,
        'raw_earnings': earning_items,
        'raw_deductions': deduction_items,
        'payment_details': payment_details,
        # Period info
        'month_display': payslip.month_name,
        'year_display': payslip.year,
    }
    return render(request, 'employees/payslip_detail.html', context)
    return render(request, 'employees/payslip_detail.html', context)


@login_required(login_url='login')
def export_payslip_pdf(request, payslip_id):
    """توليد ملف PDF لقسمية الراتب عبر WeasyPrint."""
    payslip = get_object_or_404(_payslip_queryset(), pk=payslip_id)
    if not _can_view_payslip(request.user, payslip):
        messages.error(request, 'لا يمكنك تنزيل قسيمة راتب موظف آخر.')
        return redirect('employees:payslip_detail', payslip_id=payslip.id)

    employee = payslip.employee
    filename = f"payslip_{employee.employee_number or employee.id}_{payslip.year}_{payslip.month:02d}.pdf"

    try:
        from weasyprint import HTML
        html = render_to_string('employees/payslip_pdf.html', {
            'payslip': payslip,
            'employee': employee,
            'gross_salary': payslip.basic_salary + payslip.total_earnings,
            'total_earnings': payslip.total_earnings,
            'total_deductions': payslip.total_deductions,
            'net_salary': payslip.net_salary,
        }, request=request)
        pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    except Exception as exc:
        messages.error(request, f'تعذر إنشاء ملف PDF: {exc}')
        return redirect('employees:payslip_detail', payslip_id=payslip.id)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response