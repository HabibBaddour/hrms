from django.db import models

class PerformanceEvaluation(models.Model):
    EVALUATION_TYPES = (
        ('COMPETENCIES', 'المهارات الوظيفية وجودة العمل (Job Competencies)'),
        ('BEHAVIORAL', 'السلوك والالتزام التنظيمي (Behavioral & Discipline)'),
        ('KPI_PRODUCTIVITY', 'الأهداف والإنتاجية (KPIs & Productivity)'),
        ('INITIATIVE_GROWTH', 'التطوير والمبادرة (Initiative & Growth)'),
    )
    PERIOD_TYPES = (
        ('ANNUAL', 'سنوي'),
        ('SEMI_ANNUAL', 'نصف سنوي'),
    )
    STATUS_CHOICES = (
        ('DRAFT', 'مسودة'),
        ('COMPLETED', 'مكتمل'),
    )
    # تم استبدال الاستيراد المباشر بالمرجع النصي 'employees.Employee'
    title = models.CharField(max_length=255, default='تقييم أداء', verbose_name="عنوان التقييم")
    evaluation_type = models.CharField(
        max_length=30,
        choices=EVALUATION_TYPES,
        default='COMPETENCIES',
        verbose_name='نوع التقييم / المحور الرئيسي',
    )
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='evaluations', verbose_name="الموظف")
    evaluator = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, related_name='given_evaluations', verbose_name="المقيِّم (المدير)")
    evaluation_date = models.DateField(auto_now_add=True, verbose_name="تاريخ التقييم")
    period = models.CharField(max_length=50, verbose_name="فترة التقييم (مثال: Q1 2026)")
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES, default='ANNUAL', verbose_name='نوع الفترة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED', verbose_name='الحالة')
    
    # التقييمات من 1 إلى 5، وتستخدم القيم الصفرية للمسودات غير المكتملة.
    work_quality = models.PositiveIntegerField(verbose_name="جودة العمل (1-5)")
    commitment = models.PositiveIntegerField(verbose_name="الالتزام والانضباط (1-5)")
    cooperation = models.PositiveIntegerField(verbose_name="التعاون والعمل الجماعي (1-5)")
    overall_score = models.FloatField(verbose_name="النتيجة الإجمالية", editable=False)
    question_schema = models.JSONField(
        default=list,
        blank=True,
        verbose_name="أسئلة التقييم",
    )

    departments = models.ManyToManyField(
        'departments.Department',
        blank=True,
        related_name='performance_evaluations',
        verbose_name="الأقسام المستهدفة",
    )

    feedback = models.TextField(blank=True, verbose_name="ملاحظات المدير")
    employee_feedback = models.TextField(blank=True, verbose_name='رد الموظف')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تقييم أداء"
        verbose_name_plural = "تقييمات الأداء"

    def save(self, *args, **kwargs):
        scores = (self.work_quality, self.commitment, self.cooperation)
        dynamic_scores = [
            question.get('rating')
            for question in (self.question_schema or [])
            if question.get('rating') is not None
        ]
        if dynamic_scores:
            self.overall_score = round(sum(dynamic_scores) / len(dynamic_scores), 2)
            legacy_scores = (dynamic_scores + [0, 0, 0])[:3]
            self.work_quality, self.commitment, self.cooperation = legacy_scores
        else:
            self.overall_score = 0 if all(score == 0 for score in scores) else round(sum(scores) / 3, 2)
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        for field in ('work_quality', 'commitment', 'cooperation'):
            score = getattr(self, field)
            if self.question_schema and any(
                question.get('rating') is not None for question in self.question_schema
            ):
                continue
            if self.status == 'DRAFT' and score == 0:
                continue
            if score < 1 or score > 5:
                raise ValidationError({field: 'يجب أن تكون الدرجة بين 1 و5.'})

    def __str__(self):
        return f"تقييم {self.employee} - {self.period}"


class QuestionCategory(models.Model):
    """أحد محاور تقييم الأداء التي تُبنى ضمنها الأسئلة."""

    code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name='رمز المحور',
    )
    name = models.CharField(max_length=120, verbose_name='اسم المحور')
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='الترتيب',
    )

    class Meta:
        ordering = ('order', 'pk')
        verbose_name = 'محور تقييم'
        verbose_name_plural = 'محاور التقييم'

    def __str__(self):
        return self.name


class PerformanceQuestion(models.Model):
    """سؤال تقييم مرتبط بمحور محدد وبسجل التقييم الرئيسي."""

    evaluation = models.ForeignKey(
        PerformanceEvaluation,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='التقييم',
    )
    category = models.ForeignKey(
        QuestionCategory,
        on_delete=models.PROTECT,
        related_name='questions',
        verbose_name='المحور',
    )
    text = models.CharField(max_length=500, verbose_name='نص السؤال')
    max_score = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='الدرجة القصوى',
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='الترتيب',
    )
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='التقييم',
    )

    class Meta:
        ordering = ('order', 'pk')
        verbose_name = 'سؤال تقييم'
        verbose_name_plural = 'أسئلة التقييم'

    def __str__(self):
        return f'{self.category.name}: {self.text[:50]}'