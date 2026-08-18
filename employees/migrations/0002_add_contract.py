# Generated manually to fix missing Contract table and column issues

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0001_initial'),
    ]

    operations = [
        # حذف الجداول القديمة غير المتطابقة
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS employees_contract CASCADE;",
            reverse_sql=""
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS employees_employee CASCADE;",
            reverse_sql=""
        ),
        # إعادة إنشاء الجداول بشكل صحيح
        migrations.RunSQL(
            sql="""
            CREATE TABLE employees_employee (
                id BIGSERIAL PRIMARY KEY,
                national_id VARCHAR(50) NULL,
                phone VARCHAR(20) NULL,
                department_id BIGINT NULL,
                position_id BIGINT NULL,
                user_id INTEGER NULL UNIQUE,
                CONSTRAINT employees_employee_department_id_410c23c8_fk_departmen 
                    FOREIGN KEY (department_id) 
                    REFERENCES departments_department(id) 
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
                CONSTRAINT employees_employee_position_id_19059adb_fk_departmen 
                    FOREIGN KEY (position_id) 
                    REFERENCES departments_position(id) 
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
                CONSTRAINT employees_employee_user_id_27bed289_fk_auth_user_id 
                    FOREIGN KEY (user_id) 
                    REFERENCES auth_user(id) 
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
            );
            CREATE INDEX employees_employee_department_id_410c23c8 ON employees_employee(department_id);
            CREATE INDEX employees_employee_position_id_19059adb ON employees_employee(position_id);
            """,
            reverse_sql="DROP TABLE employees_employee CASCADE;"
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE employees_contract (
                id BIGSERIAL PRIMARY KEY,
                contract_type VARCHAR(20) NOT NULL DEFAULT 'full_time',
                salary NUMERIC(10, 2) NOT NULL,
                start_date DATE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                employee_id BIGINT NOT NULL UNIQUE,
                CONSTRAINT employees_contract_employee_id_89b67511_fk_employees 
                    FOREIGN KEY (employee_id) 
                    REFERENCES employees_employee(id) 
                    ON DELETE CASCADE
            );
            """,
            reverse_sql="DROP TABLE employees_contract CASCADE;"
        ),
    ]