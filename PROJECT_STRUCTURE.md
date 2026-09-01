# هيكل المشروع Technical Reference — Django HRMS

> نظام إدارة الموارد البشرية (HRMS) مبني على **Django 6.0.7**، يستخدم **PostgreSQL** كقاعدة بيانات، واجهة **Bootstrap 5.3.2 RTL**، وطباعة PDF عبر **WeasyPrint** / **ReportLab**.
> المعمارية تتبع نمط **_function-based views** مع تطبيقات (apps) أفقية (flat layout) و不是一个 (`apps/`).

---

## 1. معمارية الجذر Root Architecture

### 1.1 شجرة الملفات الكاملة

```
hrms_project/
├── manage.py                          # نقطة الدخول الأساسية (Django management)
├── requirements.txt                   # المتطلبات (Django 6.0.7, WeasyPrint, ReportLab, Pillow)
├── requierments.txt                   # نسخة مكررة (typo)
│
├── hrms/                              # ← مجلد المشروع (Project Configuration)
│   ├── __init__.py
│   ├── settings.py                    # إعدادات Django الرئيسية
│   ├── urls.py                        # دالة التوجيه الجذرية (ROOT_URLCONF)
│   ├── wsgi.py                        # نقطة الدخول WSGI
│   └── asgi.py                        # نقطة الدخول ASGI
│
├── core/                              # ← التطبيق العام (Models, Signals, Notifications)
├── accounts/                          # ← المصادقة (Login/Logout + Attendance auto-tracking)
├── departments/                       # ← الأقسام والمناصب
├── employees/                         # ← الموظفون، العقود، كشوف الرواتب
├── attendance/                        # ← سجلات الحضور والانصراف
├── leaves/                            # ← طلبات الإجازات
├── payroll/                           # ← مسيرات الرواتب الشهرية
├── performance/                       # ← تقييمات الأداء المتعددة التصنيفات
├── reports/                           # ← لوحة التقارير
├── dashboard/                         # ← لوحات التحكم (HR / Manager / Employee + Messaging)
│
├── templates/                         # ← قالب الجذر (base.html + partials)
│   ├── base.html
│   ├── accounts/settings.html
│   ├── core/notification_list.html
│   └── messages/
│       ├── message_list.html
│       ├── message_detail.html
│       └── message_compose.html
│
├── media/                             # ← الملفات المرفوعة (صور الموظفين, العقود, الإجازات)
└── venv/                              # ← بيئة التطوير المحلية (venv)
```

### 1.2 شرح ملفات الإعدادات الجذرية

| الملف | الوظيفة |
|---|---|
| `manage.py` | نقطة الدخول الأساسية; يُحدّد `DJANGO_SETTINGS_MODULE='hrms.settings'`; يوفّر أوامر `runserver`, `migrate`, `test`, `createsuperuser` |
| `hrms/settings.py` | الإعدادات الرئيسية (详见 Section 1.3) |
| `hrms/urls.py` | التوجيه الجذرية `ROOT_URLCONF`; يربط `admin/`, `login/`, `logout/`, وكل تطبيق عبر `include()`; يخدم `media/` في وضع `DEBUG` |
| `hrms/wsgi.py` | نقطة الدخول WSGI للاستضافة (Gunicorn, uWSGI) |
| `requirements.txt` | المتطلبات: `django>=6.0.7`, `weasyprint`, `reportlab`, `Pillow` |

### 1.3 تفاصيل `hrms/settings.py`

| القسم | القيمة الرئيسية |
|---|---|
| `SECRET_KEY` | مفتاح تطوير (يجب إخفاؤه في الإنتاج عبر `.env`) |
| `DEBUG` | `True` (وضع التطوير) |
| `ALLOWED_HOSTS` | `['localhost', '127.0.0.1', 'testserver']` |
| `INSTALLED_APPS` | 10 تطبيقات مشروع + 6 تطبيقات Django مدمجة |
| `DATABASES` | PostgreSQL: `hrms_db`, `localhost:5432` |
| `ROOT_URLCONF` | `'hrms.urls'` |
| `LOGIN_URL` | `'login'` |
| `LOGIN_REDIRECT_URL` | `'dashboard'` |
| `LOGOUT_REDIRECT_URL` | `'login'` |
| `STATIC_URL` | `'static/'` |
| `MEDIA_URL` | `'/media/'` |
| `MEDIA_ROOT` | `BASE_DIR / 'media'` |
| `TEMPLATES.DIRS` | `[BASE_DIR / 'templates']` + `APP_DIRS=True` |
| Context Processors | `notifications_context` من `core.context_processors` يحقن: `unread_notifications_count`, `recent_notifications`, `user_role` (`'Employee' | 'Manager' | 'HR Admin'`), `latest_payslip_id` |

### 1.4 بنية التطبيقات (INSTALLED_APPS)

```
┌─────────────────────────────────────────────────────┐
│                  Django Built-in Apps                │
│  admin | auth | contenttypes | sessions | messages   │
│                   staticfiles                        │
├─────────────────────────────────────────────────────┤
│                   Project Apps                       │
│  accounts  │ employees │ departments │ leaves        │
│  payroll   │ performance │ reports  │ dashboard      │
│  core      │ attendance                              │
└─────────────────────────────────────────────────────┘
```

---

## 2. تفصيل كل تطبيق (App-by-App Breakdown)

---

### 2.1 `core/` — التطبيق العام (Models, Notifications, Utilities)

> يحتوي على النماذج المشتركة: الإشعارات/SystemNotification والرسائل/InternalMessage.

```
core/
├── __init__.py
├── models.py          # SystemNotification + InternalMessage
├── views.py           # notification_list, mark_notification_read, mark_all_read
├── urls.py            # app_name = 'core'
├── signals.py         # إشارات معطلة (disabled) + دوال مساعدة
├── context_processors.py  # notifications_context (يُحقن في جميع القوالب)
└── admin.py           # (فارغ)
```

#### `core/models.py` — النماذج

**`SystemNotification`**

| الحقل | النوع | التفاصيل |
|---|---|---|
| `recipient` | `ForeignKey(User)` | `CASCADE` → `related_name='system_notifications'` |
| `actor` | `ForeignKey(User)` | `SET_NULL, null=True` → `related_name='sent_notifications'` |
| `verb` | `CharField(50)` | `choices=VERB_CHOICES` (`created`, `updated`, `deleted`, `assigned`, `submitted`, `approved`, `rejected`) |
| `target` | `GenericForeignKey` | `target_content_type` + `target_object_id` — يربط الإشعار بأي كائن في النظام |
| `notification_type` | `CharField(20)` | `SYSTEM | EMPLOYEE | DEPARTMENT | LEAVE | PAYROLL` |
| `message` | `TextField` | نص الإشعار |
| `is_read` | `BooleanField` | `default=False` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

| الدالة | الوظيفة |
|---|---|
| `mark_as_read()` | يضبط `is_read=True` ويخزّن |
| `create_notification(recipient, actor, verb, message, ...)` | `@classmethod` — مصنع لإنشاء إشعار + تعيين `GenericForeignKey` اختياري |
| `get_unread_count(user)` | `@classmethod` — يُرجع عدد الإشعارات غير المقروءة |
| `get_recent_notifications(user, limit=10)` | `@classmethod` — آخر إشعارات مع `select_related('actor')` |
| `mark_all_as_read(user)` | `@classmethod` — تحديث جماعي `is_read=True` |
| `get_notification_type_color()` | لون Bootstrap حسب `notification_type` |
| `get_notification_type_display()` | اسم عربي للنوع |
| `get_target_url()` | يحلّ URL من `GenericForeignKey` |

**`InternalMessage`**

| الحقل | النوع | التفاصيل |
|---|---|---|
| `sender` | `ForeignKey(User)` | `CASCADE` → `related_name='sent_messages'` |
| `recipient` | `ForeignKey(User)` | `CASCADE` → `related_name='received_messages'` |
| `subject` | `CharField(200)` | عنوان الرسالة |
| `body` | `TextField` | محتوى الرسالة (HTML مُنقّى) |
| `is_read` | `BooleanField` | `default=False` |
| `read_at` | `DateTimeField` | `null=True` — يُحدَّث عند القراءة |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

| الدالة | الوظيفة |
|---|---|
| `mark_as_read()` | يضبط `is_read=True` + `read_at=timezone.now()` |
| `get_unread_count(user)` | `@classmethod` — عدد الرسائل غير المقروءة |
| `get_conversation(user1, user2)` | `@classmethod` — محادثة ثنائية (`Q` filter) مرتبة بـ `created_at` |

**الفهرسات (Indexes):**
- `(recipient, is_read)` — للإشعارات والرسائل
- `(notification_type)` — للإشعارات
- `(sender, created_at)` — للرسائل المرسلة
- `(created_at)` — للإشعارات

#### `core/views.py` — العروض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `notification_list` | GET | `@login_required` | `core/notification_list.html` | قائمة الإشعارات مع فلاتر: النوع، حالة القراءة، Importance (high/normal/low)، الفترة (اليوم/الأسبوع/الشهر)، البحث النصي |
| `mark_notification_read` | POST | `@login_required` | JSON / Redirect | يُعلّم إشعاراً واحداً كمقروء |
| `mark_all_read` | POST | `@login_required` | JSON / Redirect | يُعلّم جميع الإشعارات كمقروءة |

#### `core/signals.py` — الإشارات

> **جميع الإشارات معطلة (disabled).** الإشعارات تُنشأ يدوياً من العروض للتحكم الأفضل.

| الإشارة (معطلة) | الإرسال | ما كان سيفعله |
|---|---|---|
| `notify_department_created` | `post_save` → `Department` | إشعار HR عند إنشاء قسم جديد |
| `notify_position_created` | `post_save` → `Position` | إشعار HR عند إنشاء منصب جديد |
| `notify_employee_created` | `post_save` → `Employee` | إشعار HR عند إضافة موظف |
| `notify_leave_request` | `post_save` → `LeaveRequest` | إشعار HR + المدير عند تقديم طلب إجازة |
| `notify_leave_status_change` | `post_save` → `LeaveRequest` | إشعار الموظف عند تغيير حالة الإجازة |

**دوال مساعدة فعّالة:**
- `get_hr_users()` — يُرجع جميع المستخدمين في المجموعة `'HR'` + المشرفين (superusers)
- `get_managers()` — يُرجع جميع المستخدمين في المجموعة `'Manager'`

#### `core/context_processors.py`

```python
notifications_context(request) → {
    'unread_notifications_count': int,
    'recent_notifications': list[SystemNotification],
    'user_role': str,              # 'Employee' | 'Manager' | 'HR Admin'
    'latest_payslip_id': int|None,
}
```

> يُحقّن في جميع القوالب عبر `TEMPLATES[0]['OPTIONS']['context_processors']`.

#### `core/urls.py`

```
core/notifications/                  → notification_list
core/notifications/<id>/read/        → mark_notification_read
core/notifications/mark-all-read/    → mark_all_read
```

---

### 2.2 `accounts/` — المصادقة (Authentication)

> يحتوي على `CustomLoginView` + `CustomLogoutView` مع تتبع تلقائي للحضور (auto-attendance).

```
accounts/
├── __init__.py
├── models.py          # (فارغ — لا نماذج مخصصة)
├── views.py           # CustomLoginView, CustomLogoutView
├── urls.py            # (لا يُعرّف app_name)
├── templates/accounts/login.html
└── admin.py           # (فارغ)
```

#### `accounts/views.py` — العروض

| العرض | النوع | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `CustomLoginView` | CBV (`LoginView`) | عام (يُعيد توجيه المصادقين إلى `/dashboard/`) | `accounts/login.html` | POST: يدعم تسجيل الدخول بالبريد الإلكتروني (`@` → lookup by email); بعد النجاح يستدعي `AttendanceLog.record_checkin(user)` لتسجيل حضور تلقائي |
| `CustomLogoutView` | CBV (`LogoutView`) | عام | Redirect → `login` | قبل تسجيل الخروج يستدعي `AttendanceLog.record_checkout(request.user)` لتسجيل انصراف تلقائي |

**média الإعدادات في `settings.py`:**
```
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
```

#### `accounts/urls.py`

```
''                      → CustomLoginView (home)
login/                  → CustomLoginView
accounts/login/         → CustomLoginView
logout/                 → CustomLogoutView
```

---

### 2.3 `departments/` — الأقسام والمناصب (Departments & Positions)

> إدارة الهيكل التنظيمي: الأقسام (Department) والمناصب (Position) مع ربط المجموعات (auth.Group) والأدوار (roles).

```
departments/
├── __init__.py
├── models.py          # Department, Position
├── views.py           # 9 عروض (CRUD كامل)
├── urls.py            # app_name = 'departments'
├── templates/departments/
│   ├── department_list.html
│   ├── department_detail.html
│   ├── add_department.html
│   ├── edit_department.html
│   ├── department_delete.html
│   ├── add_position.html
│   ├── edit_position.html
│   └── position_detail.html
└── admin.py           # DepartmentAdmin, PositionAdmin
```

#### `departments/models.py` — النماذج

**`Department`**

| الحقل | النوع | القيود |
|---|---|---|
| `name` | `CharField(100)` | `unique=True` |
| `code` | `CharField(10)` | `unique=True` |
| `description` | `TextField` | `blank=True, null=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

**`Position`**

| الحقل | النوع | القيود |
|---|---|---|
| `title` | `CharField(100)` | — |
| `department` | `ForeignKey(Department)` | `CASCADE` → `related_name='positions'` |
| `base_salary` | `DecimalField(10,2)` | `default=0.00` |
| `salary_min` | `DecimalField(10,2)` | `default=0.00` |
| `salary_max` | `DecimalField(10,2)` | `default=0.00` |
| `group` | `ForeignKey(auth.Group)` | `SET_NULL, null=True` — يربط بال٫أداور Django |
| `role` | `CharField(100)` | `choices=ROLE_CHOICES`: `'Employee' | 'Manager' | 'HR Admin'` |
| `is_head` | `BooleanField` | `default=False` — يُحدّد رئيس القسم |

| الخاصية | الوظيفة |
|---|---|
| `estimated_salary` | `@property` — `round(float(self.base_salary or 0), 2)` |

**إشارة فعّالة (في الملف):**
```python
@receiver(post_save, sender=Position)
def sync_position_employees_salary(sender, instance, **kwargs):
    # يُحدّث Employee.salary و Contract.salary لكل موظف في نفس المنصب
```

#### `departments/views.py` — العروض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `department_list` | GET | `@login_required` | `department_list.html` | قائمة الأقسام مع عدد الموظفين (annotated) و_name_max_headcount للرسوم البيانية |
| `add_department` | GET, POST | `@login_required` | `add_department.html` | إنشاء قسم جديد + إشعار HR |
| `department_detail` | GET, POST | `@login_required` | `department_detail.html` | تفاصيل القسم; POST: إضافة منصب مباشرة |
| `edit_department` | GET, POST | `@login_required` | `edit_department.html` | تعديل القسم + إشعار HR |
| `department_delete` | GET, POST | `@login_required` | `department_delete.html` | حذف مع فحص الأمان (لا يحذف إن وجد موظفون/مناصب) |
| `add_position` | GET, POST | `@login_required` | `add_position.html` | إنشاء منصب + التحقق من النطاق السعري |
| `edit_position` | GET, POST | `@login_required` | `edit_position.html` | تعديل المنصب + التحقق |
| `position_detail` | GET, POST | `@login_required` | `position_detail.html` | تفاصيل المنصب مع تعديل مباشر |
| `delete_position` | GET, POST | `@login_required` | Redirect | حذف مع فحص عدم وجود موظفين معيّنين |

#### `departments/urls.py`

```
departments/                                → department_list
departments/add/                            → add_department
departments/<dept_id>/                      → department_detail
departments/<dept_id>/edit/                 → edit_department
departments/<dept_id>/delete/               → department_delete
departments/positions/add/                  → add_position
departments/positions/<position_id>/        → position_detail
departments/positions/<pk>/edit/            → edit_position
departments/positions/<pk>/delete/          → delete_position
```

---

### 2.4 `employees/` — الموظفون والعقود وكشوف الرواتب (Employees, Contracts, Payslips)

> أكبر تطبيق في النظام: إدارة الموظفين من التوظيف (onboarding) إلى الفصل (offboarding)، مع كشوف رواتب تفصيلية وتصدير PDF.

```
employees/
├── __init__.py
├── models.py          # Employee, EmployeePhone, Contract, Payslip, PayslipEarning, PayslipDeduction
├── views.py           # 12 عرض (10 عام + 2 مساعد)
├── forms.py           # EmployeeOnboardingForm, EmployeeEditForm, ContractLifecycleForm
├── urls.py            # app_name = 'employees'
├── templates/employees/
│   ├── employee_list.html
│   ├── create_employee_wizard.html
│   ├── edit_employee.html
│   ├── contract_detail.html
│   ├── contract_print.html
│   ├── offboard_employee.html
│   ├── profile.html
│   ├── payslip_list.html
│   ├── payslip_detail.html
│   ├── payslip_pdf.html
│   └── payslips.html
└── admin.py           # PayslipAdmin (مع PayslipEarningInline + PayslipDeductionInline)
```

#### `employees/models.py` — النماذج

**`Employee`** — الكيان المركزي

| الحقل | النوع | القيود |
|---|---|---|
| `employee_number` | `PositiveIntegerField` | `unique=True, null=True` — يُولّد تلقائياً |
| `user` | `OneToOneField(User)` | `CASCADE` → `related_name='employee_profile'` |
| `department` | `ForeignKey(Department)` | `SET_NULL, null=True` |
| `position` | `ForeignKey(Position)` | `SET_NULL, null=True` |
| `first_name` | `CharField(100)` | — |
| `last_name` | `CharField(100)` | — |
| `gender` | `CharField(10)` | `choices: 'male' | 'female'` |
| `national_id` | `CharField(20)` | `unique=True` — مدقق: `^\d{11}$` |
| `birth_date` | `DateField` | — |
| `phone` | `CharField(20)` | مدقق: `^\d{10}$` |
| `iban` | `CharField(34)` | — |
| `salary` | `DecimalField(10,2)` | — |
| `profile_picture` | `ImageField` | `upload_to='profile_pics/'` |
| `address` | `TextField` | — |
| `emergency_contact` | `CharField(100)` | — |
| `emergency_contact_phone` | `CharField(20)` | — |

| الدالة / الخاصية | الوظيفة |
|---|---|
| `save()` | يُولّد `employee_number` تلقائياً (`last_number + 1`) |
| `get_full_name()` | يُرجع الاسم الكامل (يُقدّم حقول `user` ثم حقول `employee`) |
| `annual_remaining` | `@property` — رصيد الإجازة السنوية المتبقي |
| `sick_remaining` | `@property` — رصيد إجازة المرض المتبقي |
| `emergency_remaining` | `@property` — رصيد إجازة الطوارئ المتبقي |
| `leave_remaining(leave_type, year)` | يحسب الرصيد المتبقي لأي نوع إجازة |
| `get_profile_picture_url()` | يُرجع رابط الصورة أو `None` |

> **ملاحظة مهمة:** أرصدة الإجازات **تُحسب ديناميكياً** من عدد الإجازات المعتمدة في `LeaveRequest` — لا تُخزّن كقيمة ثابتة.

**`Contract`** — عقد الموظف

| الحقل | النوع | القيود |
|---|---|---|
| `employee` | `OneToOneField(Employee)` | `CASCADE` |
| `contract_type` | `CharField(20)` | `Full-Time | Part-Time | Fixed-Term | Internship` |
| `salary` | `DecimalField(10,2)` | — |
| `start_date` | `DateField` | — |
| `end_date` | `DateField` | `null=True` |
| `status` | `CharField(20)` | `ACTIVE | EXPIRED | TERMINATED | RESIGNED` |
| `document` | `FileField` | `upload_to='contracts/%Y/%m/'` |
| `termination_date` | `DateField` | `null=True` |
| `termination_reason` | `TextField` | — |
| `clearance_status` | `CharField(30)` | `PENDING | IN_PROGRESS | CLEARED` |

**`Payslip`** — كشوف الرواتب

| الحقل | النوع | القيود |
|---|---|---|
| `employee` | `ForeignKey(Employee)` | `CASCADE` → `related_name='payslips'` |
| `month` | `PositiveIntegerField` | — |
| `year` | `PositiveIntegerField` | — |
| `basic_salary` | `DecimalField(10,2)` | — |

| الخاصية | الحساب |
|---|---|
| `month_name` | اسم الشهر بالعربي من `MONTH_NAMES` dict |
| `total_earnings` | `self.earnings.aggregate(Sum('amount'))` |
| `total_deductions` | `self.deductions.aggregate(Sum('amount'))` |
| `net_salary` | `basic_salary + total_earnings - total_deductions` |

**`PayslipEarning` / `PayslipDeduction`** — بنود الراتب

| الحقل | النوع |
|---|---|
| `payslip` | `ForeignKey(Payslip)` — `CASCADE` |
| `title` | `CharField(120)` |
| `amount` | `DecimalField(10,2)` |

**`EmployeePhone`** — أرقام الهواتف

| الحقل | النوع |
|---|---|
| `employee` | `ForeignKey(Employee)` — `CASCADE` |
| `number` | `CharField(20)` |
| `label` | `CharField(50)` — `default='Mobile'` |
| `is_primary` | `BooleanField` |

#### `employees/views.py` — العروض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `employee_list` | GET | `@login_required` | `employee_list.html` | قائمة الموظفين مع فلاتر (قسم، نوع العقد، دور، بحث) وترتيب; المدير يرى فريقه فقط |
| `get_positions_by_department` | GET | `@login_required` | JSON | API: المناصب المتاحة لقسم معين (لاست hailed AJAX) |
| `create_employee_wizard` | GET, POST | `@login_required` | `create_employee_wizard.html` | نموذج متعدد الخطوات: إنشاء User + Employee + Contract + إشعار HR; يولّد `username` و `password` تلقائياً |
| `edit_employee` | GET, POST | `@login_required` + HR/superuser | `edit_employee.html` | تعديل الموظف + User + Contract + تحديث المجموعة (Group) حسب الدور |
| `user_profile` | GET, POST | `@login_required` | `profile.html` | الملف الشخصي: صورة، معلومات، تغيير كلمة المرور |
| `contract_detail` | GET, POST | `@login_required` + HR/superuser | `contract_detail.html` | عرض/تعديل العقد |
| `contract_print` | GET | `@login_required` + HR/صاحب العقد | `contract_print.html` | نسخة قابلة للطباعة من العقد |
| `offboard_employee` | GET, POST | `@login_required` + HR/superuser | `offboard_employee.html` | إنهاء الخدمة: تعطيل الحساب + تحديث حالة العقد |
| `payslip_list_view` | GET | `@login_required` | `payslip_list.html` | كشوف رواتب الموظف الحالي |
| `payslip_detail_view` | GET | `@login_required` + صاحب الكشف/HR | `payslip_detail.html` | تفاصيل كشف الراتب مع تصنيف البنود (مزايا/خصومات) |
| `export_payslip_pdf` | GET | `@login_required` + صاحب الكشف/HR | PDF (WeasyPrint) | تصدير كشف الراتب كملف PDF |

#### `employees/forms.py` — النماذج

| النموذج | Model | الحقول الرئيسية | التحقق المخصص |
|---|---|---|---|
| `EmployeeOnboardingForm` | `Employee` | first_name, last_name, gender, national_id, birth_date, phone, email, department, position, contract_type, salary, iban, emergency_* | `clean_national_id()` — يُعيد `None` إذا فارغ |
| `EmployeeEditForm` | `Employee` | first_name, last_name, email, national_id, phone, department, position, contract_type, salary, start_date | `save()` — يحدّث User + Contract + Employee في `transaction.atomic()` |
| `ContractLifecycleForm` | `Contract` | contract_type, salary, dates, status, document, termination_* | `clean()` — `end_date >= start_date`; إذا TERMINATED/RESIGNED → `termination_date` مطلوب |

#### `employees/urls.py`

```
employees/                       → employee_list
employees/add-wizard/            → add_employee_wizard
employees/<pk>/edit/             → edit_employee
employees/<pk>/contract/         → contract_detail
employees/<pk>/contract/print/   → contract_print
employees/<pk>/offboard/         → offboard_employee
employees/profile/               → user_profile
employees/payslips/              → payslip_list
employees/payslips/<id>/         → payslip_detail
employees/payslips/<id>/pdf/     → payslip_pdf
employees/api/positions/         → get_positions_by_department
```

---

### 2.5 `attendance/` — سجلات الحضور والانصراف (Attendance)

> تتبع الحضور التلقائي عند تسجيل الدخول/الخروج.

```
attendance/
├── __init__.py
├── models.py          # AttendanceLog
├── views.py           # attendance_list_view + exports
├── urls.py            # app_name = 'attendance'
├── templates/attendance/attendance_list.html
└── admin.py           # AttendanceLogAdmin
```

#### `attendance/models.py` — النموذج

**`AttendanceLog`**

| الحقل | النوع | القيود |
|---|---|---|
| `employee` | `ForeignKey(User)` | `CASCADE` → `related_name='attendance_logs'` |
| `date` | `DateField` | — |
| `check_in` | `DateTimeField` | `null=True` |
| `check_out` | `DateTimeField` | `null=True` |
| `status` | `CharField(20)` | `present | late | absent` (قيم عربية) |

| الدالة / الخاصية | الوظيفة |
|---|---|
| `day_name` | `@property` — اسم اليوم بالعربي |
| `get_working_hours()` | ساعات العمل الكاشطة (ساعات عشرية) |
| `working_hours` | `@property` — `timedelta` |
| `working_hours_display` | `@property` — صيغة `HH:MM` |
| `record_checkin(user)` | `@staticmethod` — `get_or_create` لسجل اليوم + تعيين `check_in` |
| `record_checkout(user)` | `@staticmethod` — العثور على سجل اليوم + تعيين `check_out` (فقط إذا كان لاحقاً) |

**دورة حياة الحضور:**
1. `CustomLoginView.post()` ← `AttendanceLog.record_checkin(user)` → ينشئ سجل يومي ويضبط `check_in`
2. `CustomLogoutView.dispatch()` ← `AttendanceLog.record_checkout(user)` → يُحدّث `check_out`

#### `attendance/views.py` — العرض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `attendance_list_view` | GET | `@login_required` | `attendance_list.html` أو CSV/PDF | سجل حضور الموظف مع فلاتر الشهر/السنة; حساب `days_present` و `total_working_hours`; تصدير Excel (CSV + BOM) أو PDF (WeasyPrint) |

---

### 2.6 `leaves/` — طلبات الإجازات (Leave Requests)

> نظام الإجازات مع تنبؤ AI (محاكاة)، وtrfs فلاتر RBAC متقدمة.

```
leaves/
├── __init__.py
├── models.py          # LeaveRequest
├── views.py           # 5 عروض + predict_leave_status
├── signals.py         # signal معطّل (no-op)
├── urls.py            # app_name = 'leaves'
├── templates/leaves/
│   ├── leave_list.html
│   ├── leave_detail.html
│   ├── leave_confirm_delete.html
│   ├── apply_leave.html
│   └── approve_leave.html
└── admin.py           # LeaveRequestAdmin
```

#### `leaves/models.py` — النموذج

**`LeaveRequest`**

| الحقل | النوع | القيود |
|---|---|---|
| `employee` | `ForeignKey(Employee)` | `CASCADE` → `related_name='leave_requests'` |
| `leave_type` | `CharField(15)` | `ANNUAL | SICK | UNPAID | EMERGENCY` (TextChoices) |
| `start_date` | `DateField` | — |
| `end_date` | `DateField` | — |
| `reason` | `TextField` | — |
| `attachment` | `FileField` | `upload_to='leave_attachments/'` |
| `status` | `CharField(10)` | `PENDING | APPROVED | REJECTED` (TextChoices) |
| `ai_prediction` | `CharField(20)` | `APPROVED | REJECTED | PENDING` — محاكاة AI |
| `ai_confidence` | `FloatField` | `default=0.0` |
| `approved_by` | `ForeignKey(Employee)` | `SET_NULL, null=True` → `related_name='approved_leaves'` |
| `manager_notes` | `TextField` | `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

| الخاصية | الحساب |
|---|---|
| `total_days` | `@property` — `(end_date - start_date).days + 1` |

**альных الإجازات ((Employee model):**
- كل نوع له حصّة ثابتة: `DEFAULT_ANNUAL_LEAVE = 11`, `DEFAULT_SICK_LEAVE = 11`, `DEFAULT_EMERGENCY_LEAVE = 11`
- الإجمالي: `TOTAL_LEAVE_ALLOWANCE = 33` يوم/سنة
- الرصيد المتبقي = الحصّة − إجمالي أيام الإجازة المعتمدة (`LeaveRequest` where `status='APPROVED'`)

#### `leaves/views.py` — العروض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `leave_list` | GET | `@login_required` + RBAC | `leave_list.html` أو CSV | قائمة الإجازات; HR يرى الكل; المدير يرى قسمه; الموظف يرى أوراقه; فلاتر: قسم، دور، نوع، حالة، بحث; تصدير أرصدة الإجازات CSV |
| `leave_detail_view` | GET | RBAC (صاحب الطلب/Manager/HR) | `leave_detail.html` أو JSON | تفاصيل الإجازة مع تنبؤ AI وحالة المرفق |
| `leave_delete_view` | GET, POST | RBAC (HR يحذف أيّاً; صاحب الطلب يحذف PENDING فقط) | `leave_confirm_delete.html` | حذف طلب إجازة |
| `apply_leave` | GET, POST | `@login_required` | `apply_leave.html` | تقديم طلب: تحقق من عدم التداخل، صيغة المرفق (.pdf/.jpg/.png)، استدعاء `predict_leave_status()` + `notify_leave_submitted()` |
| `approve_leave` | GET, POST | `@login_required` + HR Admin/Manager | `approve_leave.html` | اعتماد/رفض: تحديث الحالة + `approved_by` + `notify_leave_status_changed()` |

**`predict_leave_status(leave)`** — دالة مستقلة (محاكاة AI):
```python
leave.ai_prediction = 'APPROVED'
leave.ai_confidence = 88.5
```

#### `leaves/urls.py`

```
leaves/                 → leave_list
leaves/apply/           → apply_leave
leaves/<leave_id>/      → leave_detail
leaves/<leave_id>/delete/ → leave_delete
leaves/<pk>/approve/    → approve_leave
```

---

### 2.7 `payroll/` — مسيرات الرواتب (Payroll)

> حساب الرواتب الشهرية الشهرية مع تصدير PDF ومقارنة شهر-over-شهر.

```
payroll/
├── __init__.py
├── models.py          # Payroll
├── views.py           # 5 عروض
├── forms.py           # PayrollForm
├── urls.py            # (لا يُعرّف app_name)
├── templates/payroll/
│   ├── payroll_dashboard.html
│   ├── payroll_form.html
│   ├── payslip.html
│   └── my_payslips.html
└── admin.py           # PayrollAdmin
```

#### `payroll/models.py` — النموذج

**`Payroll`**

| الحقل | النوع | القيود |
|---|---|---|
| `employee` | `ForeignKey(Employee)` | `CASCADE` → `related_name='payrolls'` |
| `month` | `PositiveIntegerField` | — |
| `year` | `PositiveIntegerField` | — |
| `basic_salary` | `DecimalField(10,2)` | — |
| `allowances` | `DecimalField(10,2)` | `default=0.00` |
| `bonuses` | `DecimalField(10,2)` | `default=0.00` |
| `deductions_absence` | `DecimalField(10,2)` | `default=0.00` |
| `deductions_delay` | `DecimalField(10,2)` | `default=0.00` |
| `insurance` | `DecimalField(10,2)` | `default=0.00` |
| `other_deductions` | `DecimalField(10,2)` | `default=0.00` |
| `net_salary` | `DecimalField(10,2)` | محسوب تلقائياً |
| `status` | `CharField(10)` | `PAID | PENDING` |

| الدالة / الخاصية | الحساب |
|---|---|
| `save()` | `net_salary = (basic_salary + allowances + bonuses) - (deductions_absence + deductions_delay + insurance + other_deductions)` |
| `total_deductions` | `@property` — مجموع كل الخصومات |
| `gross_salary` | `@property` — `basic_salary + allowances + bonuses` |

#### `payroll/views.py` — العروض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `payroll_dashboard` | GET | `@login_required` | `payroll_dashboard.html` | لوحة الرواتب مع فلاتر (قسم، شهر، سنة، حالة); إنشاء صفوف افتراضية من `Employee.salary` إذا لم تكن هناك سجلات; مجاميع (إجمالي الأساس، المزايا، الخصومات، الصافي) |
| `create_payroll` | GET, POST | `@login_required` | `payroll_form.html` | إنشاء مسير راتب جديد |
| `payroll_payslip` | GET | `@login_required` | `payslip.html` | تفاصيل كشف الراتب مع مقارنة شهرية (الشهر السابق) |
| `my_payslips` | GET | `@login_required` | `my_payslips.html` | كشوف رواتب الموظف الحالي |
| `export_payroll_pdf` | GET | `@login_required` | PDF (ReportLab) | تصدير جميع مسيرات الرواتب كجدول PDF |

#### `payroll/forms.py` — النموذج

**`PayrollForm`** (ModelForm)
- حقول: `employee`, `month`, `year`, `basic_salary`, `allowances`, `bonuses`, `deductions_absence`, `deductions_delay`, `insurance`, `other_deductions`
- `clean()` — يتحقق من عدم وجود قيم سالبة

---

### 2.8 `performance/` — تقييمات الأداء (Performance Evaluations)

> نظام تقييمات متعدد التصنيفات (4 ركائز) مع أزرار ديناميكية لكل فئة، وحفظ canon `PerformanceQuestion`.

```
performance/
├── __init__.py
├── models.py          # PerformanceEvaluation, QuestionCategory, PerformanceQuestion
├── views.py           # 5 عروض + 6 دوال مساعدة
├── forms.py           # PerformanceEvaluationForm, EvaluationDispatchForm
├── urls.py            # (لا يُعرّف app_name)
├── templates/performance/
│   ├── performance_dashboard.html
│   ├── add_evaluation.html
│   ├── evaluation_detail.html
│   ├── campaign_detail.html
│   └── team_performance.html
├── admin.py           # PerformanceEvaluationAdmin (مع PerformanceQuestionInline)
│                      # QuestionCategoryAdmin
└── migrations/
    ├── 0001_initial.py
    ├── ...
    ├── 0005_performanceevaluation_departments.py
    ├── 0006_performanceevaluation_evaluation_type.py
    ├── 0007_questioncategory_performancequestion.py   # ← جديد
    └── 0008_seed_question_categories.py               # ← بيانات أولية
```

#### `performance/models.py` — النماذج

**`PerformanceEvaluation`** — التقييم الرئيسي

| الحقل | النوع | القيود |
|---|---|---|
| `title` | `CharField(255)` | عنوان الحملة |
| `evaluation_type` | `CharField(30)` | `COMPETENCIES | BEHAVIORAL | KPI_PRODUCTIVITY | INITIATIVE_GROWTH` |
| `employee` | `ForeignKey(Employee)` | `CASCADE` → `related_name='evaluations'` |
| `evaluator` | `ForeignKey(Employee)` | `SET_NULL, null=True` → `related_name='given_evaluations'` |
| `evaluation_date` | `DateField` | `auto_now_add=True` |
| `period` | `CharField(50)` | — |
| `period_type` | `CharField(20)` | `ANNUAL | SEMI_ANNUAL` |
| `status` | `CharField(20)` | `DRAFT | COMPLETED` |
| `work_quality` | `PositiveIntegerField` | 1–5 |
| `commitment` | `PositiveIntegerField` | 1–5 |
| `cooperation` | `PositiveIntegerField` | 1–5 |
| `overall_score` | `FloatField` | `editable=False` — محسوب تلقائياً |
| `question_schema` | `JSONField` | `default=list` — لقطة الأسئلة (text + max_rating + rating) |
| `departments` | `ManyToManyField(Department)` | `blank=True` → `related_name='performance_evaluations'` |
| `feedback` | `TextField` | ملاحظات المقيّم |
| `employee_feedback` | `TextField` | ملاحظات الموظف |
| `updated_at` | `DateTimeField` | `auto_now=True` |

| الدالة | الوظيفة |
|---|---|
| `save()` | إذا وجد `rating` في `question_schema` → يحسب `overall_score` من التقييمات ويعيد تعبئة `work_quality/commitment/cooperation`; وإلا يحسب المتوسط |
| `clean()` | يتحقق من أن `work_quality/commitment/cooperation` بين 1–5 (يتخطى للـ DRAFT مع 0 أو عند وجود تقييمات في `question_schema`) |

**`QuestionCategory`** — فئات الأسئلة

| الحقل | النوع | القيود |
|---|---|---|
| `code` | `CharField(30)` | `unique=True` — `COMPETENCIES | BEHAVIORAL | KPI_PRODUCTIVITY | INITIATIVE_GROWTH` |
| `name` | `CharField(120)` | الاسم بالعربي |
| `order` | `PositiveSmallIntegerField` | `default=0` — ترتيب التبويبات |

| الترتيب الافتراضي (0008) |
|---|
| 1. COMPETENCIES — كفاءات العمل |
| 2. BEHAVIORAL — السلوك والانضباط |
| 3. KPI_PRODUCTIVITY — مؤشرات الأداء والإنتاجية |
| 4. INITIATIVE_GROWTH — المبادرة والنمو |

**`PerformanceQuestion`** — أسئلة التقييم (صفوف canon)

| الحقل | النوع | القيود |
|---|---|---|
| `evaluation` | `ForeignKey(PerformanceEvaluation)` | `CASCADE` → `related_name='questions'` |
| `category` | `ForeignKey(QuestionCategory)` | `PROTECT` → `related_name='questions'` |
| `text` | `CharField(500)` | نص السؤال |
| `max_score` | `PositiveSmallIntegerField` | `default=5` |
| `order` | `PositiveSmallIntegerField` | `default=0` |
| `rating` | `PositiveSmallIntegerField` | `null=True, blank=True` — تقييم المقيّم |

#### `performance/views.py` — العروض

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `performance_dashboard` | GET | `@login_required` | `performance_dashboard.html` | لوحة التقييمات مع تجميع الحملات (`_build_campaigns`) وفلاتر |
| `campaign_detail` | GET | `@login_required` | `campaign_detail.html` | تفاصيل الحملة مع حسابات `overall_score` ديناميكية |
| `team_performance` | GET | `@login_required` | `team_performance.html` | تقييمات الفريق المعلّقة (DRAFT) |
| `add_evaluation` | GET, POST | `@login_required` | `add_evaluation.html` | إنشاء حملة تقييم: نموذج مع قسم عنوان + قائمة أقسام دايناميكية + 4 تبويبات ركائز; POST ينشئ `PerformanceEvaluation` + `PerformanceQuestion` لكل سؤال في كل قسم |
| `evaluation_detail` | GET, POST | RBAC (المقيّم المعين فقط لملء DRAFT) | `evaluation_detail.html` | عرض/ملء التقييم: POST يُحدّث `question_schema` + `PerformanceQuestion.rating` ويُغيّر الحالة إلى COMPLETED |

**التدفق الرئيسي (`add_evaluation`):**
1. يقرأ `question_schema` من POST (كل فئة لها مصفوفة `questions_<CODE>[]`)
2. يحسب `main_type` = أول فئة في ترتيب التبويبات لها أسئلة
3. لكل قسم يُنشئ `PerformanceEvaluation` منفصلة (واحدة لكل قسم)
4. لكل سؤال يُنشئ `PerformanceQuestion` مع `category` و `text` و `rating=None`

#### `performance/forms.py` — النماذج

**`PerformanceEvaluationForm`** (ModelForm)
- حقول: `employee`, `period`, `period_type`, `work_quality`, `commitment`, `cooperation`, `feedback`, `status`
- `clean()` — تحقق من 1–5 لكل حقل

**`EvaluationDispatchForm`** (Form — غير ModelForm)

| الحقل | النوع | التفاصيل |
|---|---|---|
| `departments` | `ModelMultipleChoiceField` | `Department` نشطة — dropdown متعدد + "جميع الأقسام" |
| `title` | `CharField(200)` | عنوان الحملة |
| `evaluation_type` | `ChoiceField` | `HiddenInput` — `initial='COMPETENCIES'` |
| `questions_<CODE>[]` | (dynamically read) | مصفوفة أسئلة لكل فئة من POST |

| الدالة | الوظيفة |
|---|---|
| `__init__(self, ...)` | يبني `categories`, `category_values` (بيانات POST لكل فئة)، `tab_builders` (للقالب) |
| `clean()` | يبني `cleaned_questions_by_category` و `cleaned_questions` (مسطّح); يرفع خطأ إذا لا أسئلة |
| `cleaned_questions` | `@property` — قائمة `{'text': str, 'max_rating': 5}` |

#### `performance/urls.py`

```
performance/                    → performance_dashboard
performance/add/                → add_evaluation
performance/team/               → team_performance
performance/campaign/<id>/      → campaign_detail
performance/<pk>/               → evaluation_detail
```

---

### 2.9 `reports/` — لوحة التقارير (Reports)

> تقارير إحصائية مركّزة; جميع العروض تُقدّم نفس القالب بسياق مختلف.

```
reports/
├── __init__.py
├── models.py          # (فارغ)
├── views.py           # 4 عروض
├── urls.py            # app_name = 'reports'
├── templates/reports/reports_dashboard.html
└── admin.py           # (فارغ)
```

#### `reports/views.py` — العروض

| العرض | الطريقة | الصلاحيات | السياق المُضاف |
|---|---|---|---|
| `reports_dashboard` | GET | `@login_required` | إحصائيات عامة: عدد الموظفين، الإجازات، إجمالي الرواتب، متوسط الأداء; ملخص حالات الإجازات |
| `payroll_report` | GET | `@login_required` | آخر 10 سجلات `Payroll` مع بيانات الموظف |
| `leave_report` | GET | `@login_required` | آخر 10 طلبات `LeaveRequest` |
| `performance_report` | GET | `@login_required` | آخر 10 تقييمات `PerformanceEvaluation` |

---

### 2.10 `dashboard/` — لوحات التحكم والرسائل (Dashboards & Messaging)

> أكبر ملف views (832 سطر): 3 لوحات تحكم حسب الدور + نظام رسائل داخلية مع بث جماعي.

```
dashboard/
├── __init__.py
├── models.py          # (فارغ)
├── views.py           # 7 عروض + 4 مساعدات + MessageHTMLSanitizer
├── urls.py            # (لا يُعرّف app_name)
├── templates/dashboard/
│   ├── hr_dashboard.html
│   ├── manager_dashboard.html
│   ├── employee_portal.html
│   └── index.html
└── admin.py           # (فارغ)
```

#### `dashboard/views.py` — العروض

**لوحات التحكم:**

| العرض | الطريقة | الصلاحيات | القالب | البيانات |
|---|---|---|---|---|
| `dashboard_redirect` | GET | `@login_required` | Redirect | يُوجّه حسب الدور: HR/Admin → `hr_dashboard`; Manager → `manager_dashboard`; غيرهم → `employee_dashboard` |
| `hr_dashboard` | GET | `@login_required` | `hr_dashboard.html` | إحصائيات شاملة: عدد الموظفين/الأقسام/المناصب، إجمالي الرواتب الشهرية، متوسط الأداء، تنبيهات انتهاء العقود (60 يوم)، أعياد الميلاد، آخر الأنشطة |
| `manager_dashboard` | GET | `@login_required` | `manager_dashboard.html` | إحصائيات قسم المدير: حجم الفريق، الإجازات المعلّقة/المعتمدة، تقييمات DRAFT، متوسط الأداء |
| `employee_dashboard` | GET | `@login_required` | `employee_portal.html` | بوابة شخصية: إجازات معلّقة، أرصدة الإجازات، آخر راتب، إشعارات غير مقروءة، تقييماتي |

**نظام الرسائل:**

| العرض | الطريقة | الصلاحيات | القالب | الوظيفة |
|---|---|---|---|---|
| `message_list_view` | GET | `@login_required` | `messages/message_list.html` | صندوق الوارد/المرسل: فلاتر (بحث، تاريخ، قسم، دور، مجلد، حالة); تجميع الرسائل المبثوثة في مجموعات |
| `message_compose` | GET, POST | `@login_required` | `messages/message_compose.html` | إرسال رسالة: تحديد المستلمين بالقسم/الدور/المستخدمين المحددين; `bulk_create` لـ `InternalMessage` + `SystemNotification`; دعم @mentions |
| `get_department_users` | GET | `@login_required` | JSON | API: مستخدمو أقسام محددة (AJAX) |
| `message_detail` | GET | `@login_required` | `messages/message_detail.html` | تفاصيل الرسالة مع حالة القراءة لكل مستلم وفلاتر الأقسام/الأدوار; `mark_as_read()` تلقائي للمستلم |
| `message_delete` | GET | `@login_required` | Redirect | حذف الرسالة (المرسل أو المستلم) |

**`MessageHTMLSanitizer`** — فلتر HTML:
- يسمح فقط بـ: `b`, `strong`, `i`, `em`, `u`, `br`, `div`, `p`, `span`, `mark`
- يسمح بـ: `class` محددة + `data-user-id` + `style` محدد

---

## 3. هيكل القوالب والملفات الثابتة

### 3.1 بنية القوالب (Templates)

```
templates/
├── base.html                          # ← القالب الأساسي (Bootstrap 5.3.2 RTL + FontAwesome)
│                                      #   يحتوي: sidebar, navbar, notifications dropdown, messages dropdown
│
├── accounts/
│   └── settings.html                  # إعدادات الحساب
│
├── core/
│   └── notification_list.html         # قائمة الإشعارات مع فلاتر
│
└── messages/
    ├── message_list.html              # صندوق الرسائل
    ├── message_detail.html            # تفاصيل الرسالة + حالة القراءة
    └── message_compose.html           # نموذج إرسال رسالة
```

**قوالب التطبيقات (APP_DIRS):**

```
accounts/templates/accounts/login.html
attendance/templates/attendance/attendance_list.html
dashboard/templates/dashboard/
    ├── hr_dashboard.html
    ├── manager_dashboard.html
    ├── employee_portal.html
    └── index.html
departments/templates/departments/
    ├── department_list.html
    ├── department_detail.html
    ├── add_department.html
    ├── edit_department.html
    ├── department_delete.html
    ├── add_position.html
    ├── edit_position.html
    └── position_detail.html
employees/templates/employees/
    ├── employee_list.html
    ├── create_employee_wizard.html
    ├── edit_employee.html
    ├── contract_detail.html
    ├── contract_print.html
    ├── offboard_employee.html
    ├── profile.html
    ├── payslip_list.html
    ├── payslip_detail.html
    ├── payslip_pdf.html
    └── payslips.html
leaves/templates/leaves/
    ├── leave_list.html
    ├── leave_detail.html
    ├── leave_confirm_delete.html
    ├── apply_leave.html
    └── approve_leave.html
payroll/templates/payroll/
    ├── payroll_dashboard.html
    ├── payroll_form.html
    ├── payslip.html
    └── my_payslips.html
performance/templates/performance/
    ├── performance_dashboard.html
    ├── add_evaluation.html           # ← شُيّد بالكامل: 4 تبويبات + builders + JS
    ├── evaluation_detail.html
    ├── campaign_detail.html
    └── team_performance.html
reports/templates/reports/reports_dashboard.html
```

> **المجموع:** ~40 قالب في 10 تطبيقات + قالب الجذر.

### 3.2 هيكل الملفات الثابتة (Static)

> الملفات الثابتة مقدّمة عبر Bootstrap 5.3.2 RTL CDN في `base.html`. لا يوجد `static/` مخصص في المشروع.

| المصدر | النوع |
|---|---|
| Bootstrap 5.3.2 RTL | CDN (`css/bootstrap.rtl.min.css`, `js/bootstrap.bundle.min.js`) |
| FontAwesome 6.4.0 | CDN (`all.min.css`) |
| خط عربي (Tajawal) | CDN (`fonts.googleapis.com`) |

> لا توجد ملفات CSS أو JS مخصصة (custom) — الاعتماد الكامل على CDN + inline styles في القوالب.

---

## 4. تدفقات البيانات ودورات العمل (Data Flow & Logic Lifecycles)

### 4.1 المصادقة وتتبع الحضور التلقائي

```
┌─────────────┐     POST (username+password)     ┌──────────────────┐
│  login.html │ ───────────────────────────────── │ CustomLoginView  │
└─────────────┘                                   └────────┬─────────┘
                                                           │
                                                           ▼
                                                 ┌─────────────────────┐
                                                 │ authenticate(user)  │
                                                 │ login(request, user)│
                                                 └────────┬────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────────────────┐
                                                 │ AttendanceLog.record_        │
                                                 │   checkin(user)              │
                                                 │ get_or_create(today) →       │
                                                 │   check_in=now()            │
                                                 └────────┬────────────────────┘
                                                          │
                                                          ▼
                                                 ┌──────────────────┐
                                                 │ Redirect →       │
                                                 │ dashboard_redirect│
                                                 │ → حسب الدور      │
                                                 └──────────────────┘

┌──────────────┐     GET /logout/     ┌───────────────────┐
│   أي صفحة   │ ─────────────────── │ CustomLogoutView   │
└──────────────┘                     └────────┬──────────┘
                                              │
                                              ▼
                                   ┌─────────────────────────────┐
                                   │ AttendanceLog.record_        │
                                   │   checkout(user)             │
                                   │ find(today) →                │
                                   │   check_out=max(now, old)    │
                                   └────────┬────────────────────┘
                                            │
                                            ▼
                                   ┌──────────────────────┐
                                   │ super().dispatch()   │
                                   │ → Redirect → login   │
                                   └──────────────────────┘
```

### 4.2 حساب الرواتب الشهرية وتصدير PDF

```
┌──────────────────────┐     GET      ┌────────────────────────┐
│ payroll_dashboard    │ ──────────── │ payroll_dashboard view  │
└──────────────────────┘              └────────┬───────────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
                   │ Filter by    │   │ If no records│   │ Compute      │
                   │ dept/month/  │   │ for dept,    │   │ aggregates:  │
                   │ year/status  │   │ generate     │   │ total_base,  │
                   └──────┬───────┘   │ fallback rows│   │ allowances,  │
                          │           │ from Employee│   │ deductions,  │
                          │           │ .salary      │   │ net_salary   │
                          │           └──────┬───────┘   └──────┬───────┘
                          │                  │                   │
                          └──────────────────┼───────────────────┘
                                             │
                                             ▼
                                    ┌────────────────┐
                                    │ Render template│
                                    │ + KPI cards    │
                                    └────────────────┘

              ┌──────────────────┐  GET   ┌──────────────────┐
              │ export_payroll_  │ ────── │ ReportLab PDF    │
              │ pdf              │        │ Table Generation │
              └──────────────────┘        └──────────────────┘
```

**`Payroll.save()` flow:**
```python
net_salary = (basic_salary + allowances + bonuses)
           - (deductions_absence + deductions_delay + insurance + other_deductions)
```

**`export_payslip_pdf` (employee payslip):**
```
Export → employees/payslip_pdf.html → WeasyPrint → PDF attachment
```

### 4.3 إنشاء تقييم الأداء المتعدد التصنيفات

```
┌────────────────────┐     GET      ┌─────────────────────────┐
│ add_evaluation     │ ──────────── │ _render_dispatch_form()  │
│ (performance/add/) │              │ builds: form + tab_      │
└────────────────────┘              │ builders + categories    │
                                    └────────┬────────────────┘
                                             │
                                             ▼
                                    ┌─────────────────────────┐
                                    │ Template renders:        │
                                    │ - Title field (col-lg-5) │
                                    │ - Departments dropdown   │
                                    │   (col-lg-7)             │
                                    │ - 4 Pill Tabs:           │
                                    │   COMPETENCIES           │
                                    │   BEHAVIORAL             │
                                    │   KPI_PRODUCTIVITY       │
                                    │   INITIATIVE_GROWTH      │
                                    │ - Per-tab question       │
                                    │   builders with          │
                                    │   [data-add-question]    │
                                    └─────────────────────────┘

POST payload example:
┌─────────────────────────────────────────────────────────┐
│ title: "تقييم Q1 2026"                                 │
│ departments: [1, 3, 5]                                  │
│ evaluation_type: "COMPETENCIES" (hidden)                │
│ questions_COMPETENCIES[]: ["Q1", "Q2", "Q3"]           │
│ questions_BEHAVIORAL[]: ["B1", "B2"]                   │
│ questions_KPI_PRODUCTIVITY[]: []                        │
│ questions_INITIATIVE_GROWTH[]: ["G1"]                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ add_evaluation view:                                     │
│ 1. Validate form (grouped questions)                    │
│ 2. Compute main_type = first tab with questions         │
│    (BEHAVIORAL in this case — tab order)                │
│ 3. For each department:                                 │
│    a. Resolve evaluator (dept head or manager)          │
│    b. Get active employees (excl. evaluator+managers)   │
│    c. For each employee:                                │
│       - Create PerformanceEvaluation per category:      │
│         category=BEHAVIORAL → eval1                     │
│         category=INITIATIVE_GROWTH → eval2              │
│       - question_schema = [                             │
│           {category:'BEHAVIORAL', text:'B1', ...},     │
│           {category:'BEHAVIORAL', text:'B2', ...}      │
│         ] (for eval1)                                   │
│       - Create PerformanceQuestion rows (rating=None)   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ evaluation_detail (POST by evaluator):                  │
│ 1. Verify evaluator == request.user and status == DRAFT │
│ 2. Read rating list from POST                           │
│ 3. Update question_schema[].rating = submitted values   │
│ 4. Sync PerformanceQuestion.rating in order             │
│ 5. Set status = COMPLETED                               │
│ 6. Save (trigger overall_score computation)             │
└─────────────────────────────────────────────────────────┘
```

### 4.4 الرسائل الداخلية وفلاتر المستلمين

```
┌────────────────────┐     GET      ┌─────────────────────────┐
│ message_compose    │ ──────────── │ Departments, Roles,     │
│ (dashboard/messages│              │ Users for @mentions      │
│  /compose/)        │              └─────────────────────────┘
└────────┬───────────┘
         │ POST
         ▼
┌─────────────────────────────────────────────────────────┐
│ recipient_filter = "all_users" | "specific_users" |     │
│                    "specific_departments_users"         │
│                                                         │
│ Resolution:                                             │
│ - all_users: User.objects.filter(is_active=True)        │
│ - specific_users: by selected_user_ids                  │
│ - specific_departments_users: by dept + optional roles  │
│                                                         │
│ Bulk create:                                            │
│ - InternalMessage(sender, recipient, subject, body)     │
│ - SystemNotification(recipient, actor, verb, message)   │
└─────────────────────────────────────────────────────────┘

┌────────────────────┐     GET      ┌─────────────────────────┐
│ message_list       │ ──────────── │ Combine sent + received │
│ (dashboard/messages│              │ + group broadcast msgs  │
│  /)                │              │ + filter by folder/date  │
└────────────────────┘              └─────────────────────────┘

┌────────────────────┐     GET      ┌─────────────────────────┐
│ message_detail     │ ──────────── │ Show message +          │
│ (dashboard/messages│              │ recipient read status   │
│  /<id>/)           │              │ + batch grouping (1s)   │
└────────────────────┘              └─────────────────────────┘
```

---

## 5. نموذج الصلاحيات (RBAC Model)

### 5.1 الأدوار (Roles)

| الدور | المجموعة (Group) | الصلاحيات النموذجية |
|---|---|---|
| **`HR Admin`** | `HR` | إدارة الموظفين بالكامل، الاطلاع على جميع كشوف الرواتب، اعتماد/رفض الإجازات، رؤية جميع التقييمات |
| **`Manager`** | `Manager` | إدارة فريق القسم، اعتماد إجازات القسم، ملء تقييمات الأداء لفريقه |
| **`Employee`** | `Employee` | تقديم طلبات الإجازة، رؤية كشف راتبه فقط، ملفه الشخصي |

### 5.2 فلتر الصلاحيات في العروض

```
┌──────────────────────┬───────────────────────────────────────────┐
│ نمط الفلتر           │ الأماكن المستخدمة                         │
├──────────────────────┼───────────────────────────────────────────┤
│ @login_required      │ جميع العروض (باستثناء Login/Logout)       │
│ is_superuser         │ employees (edit, contract, offboard)      │
│ is_staff             │ employees, leaves, dashboard              │
│ groups.filter('HR')  │ employees, leaves, dashboard, performance │
│ Position.role        │ employee_list scoping, dashboard routing  │
│ owner check          │ payslip, profile, leaves, messages        │
│ department scoping   │ leaves (manager), dashboard, performance  │
│ _can_review_leave()  │ leaves                                    │
│ _can_view_payslip()  │ employees (payslip views)                 │
│ evaluator same-dept  │ performance (evaluation_detail)           │
└──────────────────────┴───────────────────────────────────────────┘
```

---

## 6. جدول الـ URLs الشامل

| # | المسار | العرض | اسم الـ URL |
|---|---|---|---|
| 1 | `admin/` | `admin.site.urls` | — |
| 2 | `''` | `CustomLoginView` | `home` |
| 3 | `login/` | `CustomLoginView` | `login` |
| 4 | `logout/` | `CustomLogoutView` | `logout` |
| 5 | `dashboard/` | `dashboard_redirect` | `dashboard` |
| 6 | `dashboard/hr/` | `hr_dashboard` | `hr_dashboard` |
| 7 | `dashboard/manager/` | `manager_dashboard` | `manager_dashboard` |
| 8 | `dashboard/employee/` | `employee_dashboard` | `employee_dashboard` |
| 9 | `dashboard/main/` | `dashboard_index` | `dashboard_main` |
| 10 | `dashboard/messages/` | `message_list_view` | `message_list` |
| 11 | `dashboard/messages/compose/` | `message_compose` | `message_compose` |
| 12 | `dashboard/messages/<id>/` | `message_detail` | `message_detail` |
| 13 | `dashboard/messages/<id>/delete/` | `message_delete` | `message_delete` |
| 14 | `departments/` | `department_list` | `departments:department_list` |
| 15 | `departments/add/` | `add_department` | `departments:add_department` |
| 16 | `departments/<id>/` | `department_detail` | `departments:department_detail` |
| 17 | `departments/<id>/edit/` | `edit_department` | `departments:edit_department` |
| 18 | `departments/<id>/delete/` | `department_delete` | `departments:department_delete` |
| 19 | `departments/positions/add/` | `add_position` | `departments:add_position` |
| 20 | `departments/positions/<id>/` | `position_detail` | `departments:position_detail` |
| 21 | `departments/positions/<id>/edit/` | `edit_position` | `departments:edit_position` |
| 22 | `departments/positions/<id>/delete/` | `delete_position` | `departments:delete_position` |
| 23 | `employees/` | `employee_list` | `employees:employee_list` |
| 24 | `employees/add-wizard/` | `create_employee_wizard` | `employees:add_employee_wizard` |
| 25 | `employees/<pk>/edit/` | `edit_employee` | `employees:edit_employee` |
| 26 | `employees/<pk>/contract/` | `contract_detail` | `employees:contract_detail` |
| 27 | `employees/<pk>/contract/print/` | `contract_print` | `employees:contract_print` |
| 28 | `employees/<pk>/offboard/` | `offboard_employee` | `employees:offboard_employee` |
| 29 | `employees/profile/` | `user_profile` | `employees:profile` |
| 30 | `employees/payslips/` | `payslip_list_view` | `employees:payslip_list` |
| 31 | `employees/payslips/<id>/` | `payslip_detail_view` | `employees:payslip_detail` |
| 32 | `employees/payslips/<id>/pdf/` | `export_payslip_pdf` | `employees:payslip_pdf` |
| 33 | `attendance/` | `attendance_list_view` | `attendance:attendance_list` |
| 34 | `leaves/` | `leave_list` | `leaves:leave_list` |
| 35 | `leaves/apply/` | `apply_leave` | `leaves:apply_leave` |
| 36 | `leaves/<id>/` | `leave_detail_view` | `leaves:leave_detail` |
| 37 | `leaves/<id>/delete/` | `leave_delete_view` | `leaves:leave_delete` |
| 38 | `leaves/<pk>/approve/` | `approve_leave` | `leaves:approve_leave` |
| 39 | `payroll/` | `payroll_dashboard` | `payroll_dashboard` |
| 40 | `payroll/add/` | `create_payroll` | `create_payroll` |
| 41 | `payroll/<pk>/payslip/` | `payroll_payslip` | `payroll_payslip` |
| 42 | `payroll/my-payslips/` | `my_payslips` | `my_payslips` |
| 43 | `payroll/export-pdf/` | `export_payroll_pdf` | `payroll_export_pdf` |
| 44 | `performance/` | `performance_dashboard` | `performance_dashboard` |
| 45 | `performance/add/` | `add_evaluation` | `add_evaluation` |
| 46 | `performance/team/` | `team_performance` | `team_performance` |
| 47 | `performance/campaign/<id>/` | `campaign_detail` | `campaign_detail` |
| 48 | `performance/<pk>/` | `evaluation_detail` | `evaluation_detail` |
| 49 | `reports/` | `reports_dashboard` | `reports:reports_dashboard` |
| 50 | `reports/payroll/` | `payroll_report` | `reports:payroll_report` |
| 51 | `reports/leaves/` | `leave_report` | `reports:leave_report` |
| 52 | `reports/performance/` | `performance_report` | `reports:performance_report` |
| 53 | `core/notifications/` | `notification_list` | `core:notification_list` |
| 54 | `core/notifications/<id>/read/` | `mark_notification_read` | `core:mark_notification_read` |
| 55 | `core/notifications/mark-all-read/` | `mark_all_read` | `core:mark_all_read` |
| 56 | `settings/` | `TemplateView` | `user_settings` |

> **المجموع:** ~56 نمط URL عبر 10 ملفات `urls.py`.

---

## 7. مخطط العلاقات (Entity Relationship)

```
┌──────────────┐     1:1      ┌──────────────┐     FK      ┌──────────────┐
│  auth.User   │◄────────────│  Employee    │◄────────────│ Department   │
└──────┬───────┘              └──────┬───────┘             └──────┬───────┘
       │                             │                            │
       │ FK (AttendanceLog)          │ FK (Contract 1:1)          │ FK (Position)
       │ FK (Notification.recipient) │ FK (Payslip)               │
       │ FK (Message.sender/recv)    │ FK (LeaveRequest)          │ FK (Employee)
       │                             │ FK (Payroll)               │
       │                             │ FK (PerformanceEvaluation) │ M2M (PerformanceEval)
       │                             │ FK (EmployeePhone)         │
       │                             │                            │
       ▼                             ▼                            ▼
┌──────────────┐              ┌──────────────┐             ┌──────────────┐
│AttendanceLog │              │  Contract    │             │  Position    │
│(User FK)     │              │ (1:1 Emp)    │             │ (auth.Group) │
└──────────────┘              └──────────────┘             └──────────────┘

┌──────────────┐    FK    ┌──────────────┐    FK    ┌──────────────────┐
│Performance   │◄────────│Performance   │◄────────│ QuestionCategory │
│Evaluation    │         │Question      │         │ (code, name)     │
│(question_    │         │(evaluation,  │         └──────────────────┘
│ schema JSON) │         │ category)    │
└──────────────┘         └──────────────┘

┌──────────────┐    FK    ┌──────────────┐
│  Payslip     │◄────────│ Payslip      │
│              │         │ Earning      │
│              │◄────────│ Payslip      │
│              │         │ Deduction    │
└──────────────┘         └──────────────┘

┌──────────────────┐    GenericFK    ┌──────────────┐
│ SystemNotification│◄──────────────│ أي كائن      │
│ (recipient, actor)│               │ في النظام    │
└──────────────────┘               └──────────────┘
```

---

> **آخر تحديث:** سبتمبر 2026 — يشمل `QuestionCategory` + `PerformanceQuestion` + هجرة `0005`/`0006`/`0007`/`0008`.
