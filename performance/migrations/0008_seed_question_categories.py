from django.db import migrations

CATEGORIES = [
    ('COMPETENCIES', 'المهارات الوظيفية وجودة العمل (Job Competencies)', 1),
    ('BEHAVIORAL', 'السلوك والالتزام التنظيمي (Behavioral & Discipline)', 2),
    ('KPI_PRODUCTIVITY', 'الأهداف والإنتاجية (KPIs & Productivity)', 3),
    ('INITIATIVE_GROWTH', 'التطوير والمبادرة (Initiative & Growth)', 4),
]


def seed_categories(apps, schema_editor):
    QuestionCategory = apps.get_model('performance', 'QuestionCategory')
    for code, name, order in CATEGORIES:
        QuestionCategory.objects.update_or_create(
            code=code,
            defaults={'name': name, 'order': order},
        )


def revert_categories(apps, schema_editor):
    QuestionCategory = apps.get_model('performance', 'QuestionCategory')
    QuestionCategory.objects.filter(
        code__in=[code for code, _, _ in CATEGORIES],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('performance', '0007_questioncategory_performancequestion'),
    ]

    operations = [
        migrations.RunPython(seed_categories, revert_categories),
    ]