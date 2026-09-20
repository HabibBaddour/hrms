import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceLog
from employees.models import Employee
from leaves.models import LeaveRequest


class Command(BaseCommand):
    help = "توليد بيانات حضور عشوائية واقعية للموظفين الموجودين في قاعدة البيانات"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=6,
            help="عدد الأشهر السابقة التي سيتم توليد البيانات لها",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Seed ثابت لجعل البيانات العشوائية قابلة لإعادة الإنتاج",
        )

    def handle(self, *args, **options):
        months = options["months"]
        seed = options["seed"]

        if months <= 0:
            self.stdout.write(
                self.style.ERROR("عدد الأشهر يجب أن يكون أكبر من صفر.")
            )
            return

        rng = random.Random(seed)

        today = timezone.localdate()
        end_date = today - timedelta(days=1)
        start_date = end_date - timedelta(days=30 * months)

        employees = list(
            Employee.objects
            .select_related("user", "contract")
            .filter(user__isnull=False)
            .order_by("id")
        )

        if not employees:
            self.stdout.write(
                self.style.WARNING(
                    "لم يتم العثور على أي موظف مرتبط بحساب User."
                )
            )
            return

        # الإجازات الموافق عليها: لن ننشئ حضورًا أو غيابًا عليها.
        approved_leaves = LeaveRequest.objects.filter(
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        leave_days_by_employee = {}

        for leave in approved_leaves:
            employee_id = leave.employee_id
            employee_days = leave_days_by_employee.setdefault(
                employee_id,
                set(),
            )

            current_day = max(leave.start_date, start_date)
            leave_end = min(leave.end_date, end_date)

            while current_day <= leave_end:
                employee_days.add(current_day)
                current_day += timedelta(days=1)

        # السجلات الموجودة مسبقًا حتى لا نكررها.
        existing_logs = AttendanceLog.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            employee_id__in=[employee.user_id for employee in employees],
        ).values_list("employee_id", "date")

        existing_keys = set(existing_logs)

        new_logs = []

        total_present = 0
        total_late = 0
        total_absent = 0
        total_skipped_leave = 0
        total_skipped_existing = 0

        for employee in employees:
            user = employee.user

            # احترام فترة العقد إن كانت موجودة.
            employee_start = start_date
            employee_end = end_date

            if employee.contract:
                if employee.contract.start_date:
                    employee_start = max(
                        employee_start,
                        employee.contract.start_date,
                    )

                if employee.contract.end_date:
                    employee_end = min(
                        employee_end,
                        employee.contract.end_date,
                    )

            if employee_start > employee_end:
                continue

            current_day = employee_start

            while current_day <= employee_end:
                # الجمعة عطلة أسبوعية في النظام الحالي.
                if current_day.weekday() == 4:
                    current_day += timedelta(days=1)
                    continue

                # لا نضع حضورًا أثناء إجازة موافق عليها.
                if current_day in leave_days_by_employee.get(
                    employee.id,
                    set(),
                ):
                    total_skipped_leave += 1
                    current_day += timedelta(days=1)
                    continue

                key = (user.id, current_day)

                # عدم تكرار السجلات الموجودة مسبقًا.
                if key in existing_keys:
                    total_skipped_existing += 1
                    current_day += timedelta(days=1)
                    continue

                # توزيع تقريبي:
                # 85% حاضر
                # 10% تأخير
                # 5% غياب
                probability = rng.random()

                if probability < 0.85:
                    status = AttendanceLog.STATUS_PRESENT
                    total_present += 1

                    # دخول طبيعي قبل أو عند بداية الدوام.
                    check_in_time = time(
                        hour=8,
                        minute=rng.randint(0, 5),
                    )

                    # خروج تقريبي حول الساعة 16:00.
                    check_out_time = time(
                        hour=16,
                        minute=rng.randint(0, 15),
                    )

                elif probability < 0.95:
                    status = AttendanceLog.STATUS_LATE
                    total_late += 1

                    # دخول متأخر من 08:06 حتى 09:00.
                    check_in_time = time(
                        hour=rng.randint(8, 9),
                        minute=rng.randint(6, 59),
                    )

                    # خروج طبيعي تقريبًا.
                    check_out_time = time(
                        hour=16,
                        minute=rng.randint(0, 15),
                    )

                else:
                    status = AttendanceLog.STATUS_ABSENT
                    total_absent += 1

                    check_in_time = None
                    check_out_time = None

                check_in = None
                check_out = None

                if check_in_time:
                    check_in = timezone.make_aware(
                        datetime.combine(
                            current_day,
                            check_in_time,
                        )
                    )

                if check_out_time:
                    check_out = timezone.make_aware(
                        datetime.combine(
                            current_day,
                            check_out_time,
                        )
                    )

                new_logs.append(
                    AttendanceLog(
                        employee=user,
                        date=current_day,
                        check_in=check_in,
                        check_out=check_out,
                        status=status,
                    )
                )

                current_day += timedelta(days=1)

        if new_logs:
            AttendanceLog.objects.bulk_create(
                new_logs,
                batch_size=1000,
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "تم توليد بيانات الحضور بنجاح."
            )
        )
        self.stdout.write(f"الفترة: {start_date} إلى {end_date}")
        self.stdout.write(f"عدد الموظفين: {len(employees)}")
        self.stdout.write(f"سجلات جديدة: {len(new_logs)}")
        self.stdout.write(f"حاضر: {total_present}")
        self.stdout.write(f"تأخير: {total_late}")
        self.stdout.write(f"غائب: {total_absent}")
        self.stdout.write(f"تم تجاهلها بسبب إجازة موافق عليها: {total_skipped_leave}")
        self.stdout.write(f"تم تجاهلها لأنها موجودة مسبقًا: {total_skipped_existing}")