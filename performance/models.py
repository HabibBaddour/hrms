from django.db import models

class PerformanceEvaluation(models.Model):
    # تم استبدال الاستيراد المباشر بالمرجع النصي 'employees.Employee'
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='evaluations', verbose_name="الموظف")
    evaluator = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, related_name='given_evaluations', verbose_name="المقيِّم (المدير)")
    evaluation_date = models.DateField(auto_now_add=True, verbose_name="تاريخ التقييم")
    period = models.CharField(max_length=50, verbose_name="فترة التقييم (مثال: Q1 2026)")
    
    # التقييمات من 1 إلى 5
    work_quality = models.PositiveIntegerField(verbose_name="جودة العمل (1-5)")
    commitment = models.PositiveIntegerField(verbose_name="الالتزام والانضباط (1-5)")
    cooperation = models.PositiveIntegerField(verbose_name="التعاون والعمل الجماعي (1-5)")
    overall_score = models.FloatField(verbose_name="النتيجة الإجمالية", editable=False)
    
    feedback = models.TextField(verbose_name="ملاحظات المدير")

    class Meta:
        verbose_name = "تقييم أداء"
        verbose_name_plural = "تقييمات الأداء"

    def save(self, *args, **kwargs):
        self.overall_score = round((self.work_quality + self.commitment + self.cooperation) / 3, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"تقييم {self.employee} - {self.period}"