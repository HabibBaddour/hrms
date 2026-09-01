from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class AttendanceLog(models.Model):
    STATUS_PRESENT = 'حاضر'
    STATUS_LATE = 'تأخير'
    STATUS_ABSENT = 'غائب'

    STATUS_CHOICES = [
        (STATUS_PRESENT, 'حاضر'),
        (STATUS_LATE, 'تأخير'),
        (STATUS_ABSENT, 'غائب'),
    ]

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_logs')
    date = models.DateField(verbose_name='التاريخ')
    check_in = models.DateTimeField(null=True, blank=True, verbose_name='وقت الدخول')
    check_out = models.DateTimeField(null=True, blank=True, verbose_name='وقت الخروج')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT, verbose_name='الحالة')

    class Meta:
        ordering = ['-date', '-check_in']
        verbose_name = 'سجل الحضور'
        verbose_name_plural = 'سجلات الحضور'

    def __str__(self):
        return f"{self.employee.get_full_name() or self.employee.username} - {self.date} - {self.status}"

    @property
    def day_name(self):
        arabic_days = {
            'Saturday': 'السبت',
            'Sunday': 'الأحد',
            'Monday': 'الإثنين',
            'Tuesday': 'الثلاثاء',
            'Wednesday': 'الأربعاء',
            'Thursday': 'الخميس',
            'Friday': 'الجمعة',
        }
        return arabic_days.get(self.date.strftime('%A'), self.date.strftime('%A'))

    def get_working_hours(self):
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            if delta.total_seconds() > 0:
                return round(delta.total_seconds() / 3600, 2)
        return 0

    @property
    def working_hours(self):
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            if delta.total_seconds() > 0:
                return delta
        return timedelta(0)

    @property
    def working_hours_display(self):
        total_seconds = int(self.working_hours.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f'{hours:02d}:{minutes:02d}'

    @staticmethod
    def record_checkin(user):
        """تسجيل توقيت دخول الموظف - سجل واحد لكل يوم"""
        today = timezone.localdate()
        check_in = timezone.localtime()
        log, _ = AttendanceLog.objects.get_or_create(
            employee=user,
            date=today,
            defaults={'check_in': check_in, 'status': AttendanceLog.STATUS_PRESENT},
        )
        if log.check_in is None:
            log.check_in = check_in
            log.save(update_fields=['check_in'])
        return log

    @staticmethod
    def record_checkout(user):
        """تسجيل توقيت خروج الموظف - يُحدَّث سجل اليوم إذا وُجد"""
        today = timezone.localdate()
        try:
            log = AttendanceLog.objects.get(employee=user, date=today)
        except AttendanceLog.DoesNotExist:
            return None
        check_out = timezone.localtime()
        if log.check_out is None or check_out > log.check_out:
            log.check_out = check_out
            log.save(update_fields=['check_out'])
        return log
