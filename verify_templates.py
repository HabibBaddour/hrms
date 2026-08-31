import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms.settings')
import django
django.setup()
from django.template import Template

files = [
    Path('templates/base.html'),
    Path('dashboard/templates/dashboard/manager_dashboard.html'),
]

for path in files:
    try:
        Template(path.read_text(encoding='utf-8'))
        print(f'OK {path}')
    except Exception as exc:
        print(f'FAIL {path}: {type(exc).__name__}: {exc}')
