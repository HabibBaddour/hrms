from django.contrib import admin
from .models import Department, Position

# إلغاء التسجيل السابق إن وجد لتجنب أخطاء AlreadyRegistered
if admin.site.is_registered(Department):
    admin.site.unregister(Department)

if admin.site.is_registered(Position):
    admin.site.unregister(Position)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at')
    search_fields = ('name', 'code')


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'base_salary', 'group') # <-- أضفنا base_salary هنا
    list_filter = ('department', 'group')
    search_fields = ('title',)