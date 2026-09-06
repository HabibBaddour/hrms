"""إدارة تنظيف كشوف الرواتب والقسائم القديمة من قاعدة البيانات.

الاستخدام:
    python manage.py clean_payslips                     # حذف كل القسائم والمسيرات
    python manage.py clean_payslips --dry-run            # عرض الأعداد دون حذف
    python manage.py clean_payslips --year 2026          # فترة محددة فقط
    python manage.py clean_payslips --month 8 --year 2026
    python manage.py clean_payslips --employee 3         # موظف محدد فقط
"""

import shlex

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "حذف جميع كشوف الرواتب (Payroll) والقسائم (Payslip) لبدء قاعدة بيانات نظيفة."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month", type=int, help="حذف فترة شهر محدد فقط (1-12)",
        )
        parser.add_argument(
            "--year", type=int, help="حذف فترة سنة محددة فقط",
        )
        parser.add_argument(
            "--employee", type=int, help="حذف قسائم موظف محدد فقط (رقم الموظف)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="عرض عدد السجلات المراد حذفها دون حذف فعلي",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from employees.models import Payslip
        from payroll.models import Payroll

        filters = {}
        if options.get("month"):
            filters["month"] = options["month"]
        if options.get("year"):
            filters["year"] = options["year"]
        if options.get("employee"):
            filters["employee_id"] = options["employee"]

        payroll_qs = Payroll.objects.filter(**filters) if filters else Payroll.objects.all()
        payslip_qs = Payslip.objects.filter(**filters) if filters else Payslip.objects.all()

        payroll_count = payroll_qs.count()
        payslip_count = payslip_qs.count()

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"جاهز للحذف: Payroll = {payroll_count}، Payslip = {payslip_count}"
            ))
            return

        # الحذف بالترتيب: Payroll أولاً ليمسح القسائم المرتبطة عبر إشارة المزامنة،
        # ثم أي قسائم مستقلة خارج نظام المسير.
        payroll_qs.delete()
        payslip_qs.delete()

        self.stdout.write(self.style.SUCCESS(
            f"تم الحذف: Payroll = {payroll_count}، Payslip = {payslip_count}"
        ))