from django.db import migrations
from django.db.models import Q


def backfill_department_managers(apps, schema_editor):
    Department = apps.get_model('departments', 'Department')
    Employee = apps.get_model('employees', 'Employee')
    for dept in Department.objects.all():
        manager = (
            Employee.objects.filter(
                Q(department_id=dept.id) | Q(position__department_id=dept.id),
                position__role='Manager',
                user__is_active=True,
            )
            .order_by('-position__is_head', 'id')
            .first()
        )
        if manager:
            dept.manager = manager
            dept.save(update_fields=['manager'])


def clear_department_managers(apps, schema_editor):
    Department = apps.get_model('departments', 'Department')
    Department.objects.filter(manager__isnull=False).update(manager=None)


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0008_department_manager'),
    ]

    operations = [
        migrations.RunPython(backfill_department_managers, clear_department_managers),
    ]