import csv
from calendar import monthrange
from decimal import Decimal
from collections import defaultdict
from datetime import date, time

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceLog
from employees.models import Employee


WORK_START = time(8, 0)
WORK_HOURS_PER_DAY = 8

OUTPUT_FILE = "attendance/ml/data/attendance_dataset.csv"


class Command(BaseCommand):
    help = "بناء Dataset شهري من بيانات الحضور والرواتب الموجودة في قاعدة البيانات"

    def handle(self, *args, **options):
        employees = list(
            Employee.objects
            .select_related("user")
            .filter(user__isnull=False)
            .exclude(salary__isnull=True)
            .order_by("id")
        )

        if not employees:
            self.stdout.write(
                self.style.ERROR(
                    "لم يتم العثور على موظفين لديهم راتب."
                )
            )
            return

        employee_ids = [employee.user_id for employee in employees]

        logs = list(
            AttendanceLog.objects
            .filter(employee_id__in=employee_ids)
            .order_by("date")
        )

        if not logs:
            self.stdout.write(
                self.style.ERROR(
                    "لا توجد سجلات حضور لبناء Dataset."
                )
            )
            return

        # تحديد الفترة الفعلية الموجودة في بيانات الحضور.
        min_date = min(log.date for log in logs)
        max_date = max(log.date for log in logs)

        # نستبعد الشهر الجزئي الأول والأخير.
        first_full_month = date(
            min_date.year,
            min_date.month,
            1,
        )

        if min_date.day != 1:
            if min_date.month == 12:
                first_full_month = date(
                    min_date.year + 1,
                    1,
                    1,
                )
            else:
                first_full_month = date(
                    min_date.year,
                    min_date.month + 1,
                    1,
                )

        last_day_of_max_month = monthrange(
            max_date.year,
            max_date.month,
        )[1]

        last_full_month = date(
            max_date.year,
            max_date.month,
            last_day_of_max_month,
        )

        if max_date.day != last_day_of_max_month:
            if max_date.month == 1:
                last_full_month = date(
                    max_date.year - 1,
                    12,
                    31,
                )
            else:
                previous_month = max_date.month - 1
                previous_year = max_date.year

                last_full_month = date(
                    previous_year,
                    previous_month,
                    monthrange(
                        previous_year,
                        previous_month,
                    )[1],
                )

        if first_full_month > last_full_month:
            self.stdout.write(
                self.style.ERROR(
                    "لا توجد أشهر كاملة كافية لبناء Dataset."
                )
            )
            return

        employee_by_user_id = {
            employee.user_id: employee
            for employee in employees
        }

        monthly_logs = defaultdict(list)

        for log in logs:
            if (
                log.date < first_full_month
                or log.date > last_full_month
            ):
                continue

            key = (
                log.employee_id,
                log.date.year,
                log.date.month,
            )

            monthly_logs[key].append(log)

        dataset_rows = []

        for (user_id, year, month), employee_logs in sorted(
            monthly_logs.items()
        ):
            employee = employee_by_user_id.get(user_id)

            if not employee:
                continue

            first_day = date(year, month, 1)
            last_day = date(
                year,
                month,
                monthrange(year, month)[1],
            )

            working_days = 0

            current_day = first_day

            while current_day <= last_day:
                # الجمعة عطلة أسبوعية في النظام.
                if current_day.weekday() != 4:
                    working_days += 1

                current_day = date.fromordinal(
                    current_day.toordinal() + 1
                )

            if working_days <= 0:
                continue

            present_days = 0
            late_days = 0
            absent_days = 0
            late_minutes = 0

            for log in employee_logs:
                if log.status == AttendanceLog.STATUS_ABSENT:
                    absent_days += 1

                elif log.status == AttendanceLog.STATUS_LATE:
                    late_days += 1

                    if log.check_in:
                        check_in_local = timezone.localtime(
                            log.check_in
                        )

                        actual_minutes = (
                            check_in_local.hour * 60
                            + check_in_local.minute
                        )

                        start_minutes = (
                            WORK_START.hour * 60
                            + WORK_START.minute
                        )

                        delay = (
                            actual_minutes
                            - start_minutes
                        )

                        if delay > 0:
                            late_minutes += delay

                elif log.status == AttendanceLog.STATUS_PRESENT:
                    present_days += 1

            late_hours = Decimal(late_minutes) / Decimal("60")

            basic_salary = Decimal(str(employee.salary))

            daily_rate = (
                basic_salary / Decimal(working_days)
            )

            absence_deduction = (
                Decimal(absent_days) * daily_rate
            )

            hourly_rate = (
                daily_rate / Decimal(str(WORK_HOURS_PER_DAY))
            )

            delay_deduction = (
                late_hours * hourly_rate
            )

            absence_deduction = absence_deduction.quantize(
                Decimal("0.01")
            )

            delay_deduction = delay_deduction.quantize(
                Decimal("0.01")
            )

            total_deduction = (
                absence_deduction
                + delay_deduction
            )

            dataset_rows.append(
                {
                    "employee_id": employee.id,
                    "month": month,
                    "year": year,
                    "basic_salary": float(
                        basic_salary.quantize(Decimal("0.01"))
                    ),
                    "working_days": working_days,
                    "present_days": present_days,
                    "late_days": late_days,
                    "absent_days": absent_days,
                    "late_minutes": late_minutes,
                    "late_hours": round(
                        float(late_hours),
                        2,
                    ),
                    "absence_deduction": float(
                        absence_deduction
                    ),
                    "delay_deduction": float(
                        delay_deduction
                    ),
                    "total_deduction": float(
                        total_deduction
                    ),
                }
            )

        if not dataset_rows:
            self.stdout.write(
                self.style.ERROR(
                    "لم يتم إنشاء أي صفوف في Dataset."
                )
            )
            return

        fieldnames = [
            "employee_id",
            "month",
            "year",
            "basic_salary",
            "working_days",
            "present_days",
            "late_days",
            "absent_days",
            "late_minutes",
            "late_hours",
            "absence_deduction",
            "delay_deduction",
            "total_deduction",
        ]

        with open(
            OUTPUT_FILE,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(dataset_rows)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "تم إنشاء Dataset المصحح بنجاح."
            )
        )
        self.stdout.write(
            f"الفترة المستخدمة: {first_full_month} → {last_full_month}"
        )
        self.stdout.write(
            f"عدد الأشهر: {len(set((r['year'], r['month']) for r in dataset_rows))}"
        )
        self.stdout.write(
            f"عدد الصفوف: {len(dataset_rows)}"
        )
        self.stdout.write(
            f"الملف: {OUTPUT_FILE}"
        )