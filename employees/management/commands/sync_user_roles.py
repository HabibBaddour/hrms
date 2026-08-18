from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from employees.models import Employee


class Command(BaseCommand):
    help = 'Sync user roles with their employee position roles - enforces strict role-based access control'

    def handle(self, *args, **options):
        self.stdout.write('=== Starting User Role Synchronization ===')
        self.stdout.write('This will sync ALL user accounts to match their Employee.position.role')
        
        # Get or create groups
        hr_group, _ = Group.objects.get_or_create(name='HR')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        employee_group, _ = Group.objects.get_or_create(name='Employee')
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Get statistics before sync
        total_employees = Employee.objects.count()
        self.stdout.write(f'Total employees in database: {total_employees}')
        
        # Iterate over ALL employees
        for employee in Employee.objects.all():
            try:
                user = employee.user
                if not user:
                    self.stdout.write(f'Skipping employee {employee.id} - no user associated')
                    skipped_count += 1
                    continue
                
                position = employee.position
                if not position:
                    self.stdout.write(f'Skipping employee {employee.id} - no position assigned')
                    skipped_count += 1
                    continue
                
                position_role = position.role
                # Use ASCII-safe output to avoid encoding issues
                position_title = getattr(position, 'title', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                self.stdout.write(f'Processing: {user.username} | Position: {position_title} | Role: {position_role}')
                
                # Clear existing groups to ensure clean state
                user.groups.clear()
                
                # Set user flags and groups based on position role (STRICT enforcement)
                if position_role.lower() == 'hr admin':
                    user.is_staff = True
                    user.is_superuser = False  # HR Admin is staff but not superuser
                    user.groups.add(hr_group)
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Updated to HR Admin (is_staff=True)'))
                    
                elif position_role.lower() == 'manager':
                    user.is_staff = False
                    user.is_superuser = False
                    user.groups.add(manager_group)
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Updated to Manager (is_staff=False)'))
                    
                else:  # Employee or any other role
                    user.is_staff = False
                    user.is_superuser = False
                    user.groups.add(employee_group)
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Updated to Employee (is_staff=False)'))
                
                user.save()
                updated_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [ERROR] Failed processing employee {employee.id}: {str(e)}'))
                error_count += 1
        
        # Summary
        self.stdout.write('\n=== Synchronization Summary ===')
        self.stdout.write(self.style.SUCCESS(f'Successfully updated: {updated_count} users'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Skipped (no user/position): {skipped_count} employees'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Failed to update: {error_count} users'))
        
        self.stdout.write(self.style.SUCCESS('\nRole synchronization complete! All users now match their position roles.'))