"""
محرك تحليل طلبات الإجازات الذكي (AI Leave Analyzer).

يستخدم RandomForestClassifier عند توفر scikit-learn (مع تخزين النموذج عبر joblib)،
ويتراجع تلقائياً إلى محرك قواعد شفاف إذا لم يكن scikit-learn مثبتاً لديك.
"""

import os
import random
from datetime import date, datetime

SKLEARN_AVAILABLE = False
joblib = None
RandomForestClassifier = None

try:
    import joblib  # noqa: E402
    from sklearn.ensemble import RandomForestClassifier  # noqa: E402
    SKLEARN_AVAILABLE = True
except Exception:
    pass

_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ml_leave_model.joblib')

_FEATURES = [
    'requested_days',
    'balance_ratio',
    'dept_conflicts',
    'is_peak',
    'notice_days',
    'leave_sick',
    'leave_emergency',
    'leave_unpaid',
]

_model = None


def _overlaps(start_lo, start_hi, other_lo, other_hi):
    return start_lo <= other_hi and other_lo <= start_hi


def is_peak_period(start_date, end_date):
    """هل تقع الفترة ضمن موسم ذروة الإجازات؟ (الصيف: 1/6–31/8، ورأس السنة: 15/12–5/1)."""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    for year in range(start_date.year - 1, end_date.year + 2):
        summer = (date(year, 6, 1), date(year, 8, 31))
        holiday = (date(year, 12, 15), date(year + 1, 1, 5))
        if _overlaps(start_date, end_date, *summer) or _overlaps(start_date, end_date, *holiday):
            return True
    return False


def _analyse_features(requested_days, remaining_balance, dept_conflicts, is_peak, notice_days, leave_type):
    """تقييم قائم على قواعد الخبراء ويعيد (درجة 0–100، قائمة أسباب عربية)."""
    score = 50
    reasons = []

    if notice_days < 0:
        score -= 10
        reasons.append('تاريخ بداية الإجازة في الماضي — يُرجى تصحيح التاريخ.')

    if leave_type != 'UNPAID':
        if requested_days > remaining_balance:
            score -= 28
            reasons.append(f'الرصيد المتبقي ({remaining_balance} يوم) لا يغطي مدة الطلب ({requested_days} يوم).')
        else:
            surplus = remaining_balance - requested_days
            if surplus >= 5:
                score += 12
                reasons.append('الرصيد المتبقي ممتاز ويغطي مدة الطلب مع فائض مريح.')
            else:
                score += 6
                reasons.append('الرصيد المتبقي يغطي مدة الطلب.')
    else:
        score -= 6
        reasons.append('إجازة بدون راتب — لا تستهلك رصيد الإجازات المدفوعة.')

    if dept_conflicts == 0:
        score += 10
        reasons.append('لا يوجد تعارض مع موظفين آخرين في قسمك خلال نفس الفترة.')
    elif dept_conflicts <= 2:
        score -= 5
        reasons.append(f'يوجد {dept_conflicts} موظف في قسمك في إجازة خلال نفس الفترة — ملاحظة خفيفة.')
    else:
        score -= 22
        reasons.append(f'يوجد {dept_conflicts} موظفاً في قسمك في إجازة خلال نفس الفترة — خطر على تغطية العمل.')

    if is_peak and leave_type not in ('SICK', 'EMERGENCY'):
        score -= 10
        reasons.append('الفترة المطلوبة تقع ضمن موسم الذروة (الصيف أو رأس السنة).')
    elif not is_peak:
        score += 4
        reasons.append('الفترة المطلوبة خارج موسم الذروة.')

    if leave_type in ('SICK', 'EMERGENCY'):
        score += 4
        if notice_days <= 0:
            reasons.append('إجازة طارئة/مرضية تبدأ فوراً — تتطلب معالجة سريعة من الإدارة.')
        else:
            reasons.append('إجازة طارئة/مرضية مقدّمة بتوقيت منطقي.')
    else:
        if notice_days >= 14:
            score += 12
            reasons.append('مقدّم قبل بداية الإجازة بمدة كافية — تخطيط جيد.')
        elif notice_days >= 7:
            score += 6
            reasons.append('مقدّم قبل أسبوع أو أكثر من بداية الإجازة.')
        elif notice_days >= 3:
            reasons.append('مقدّم قبل أيام قليلة من بداية الإجازة.')
        else:
            score -= 8
            reasons.append('الفاصل الزمني قبل بداية الإجازة قصير جداً — قد يؤثر على التغطية.')

    if leave_type == 'SICK':
        score += 10
        reasons.append('إجازة مرضية — تُمنح أولوية في المعالجة.')
    elif leave_type == 'EMERGENCY':
        score += 6
        reasons.append('إجازة طارئة — تعامل بمرونة إضافية.')

    return max(5, min(98, score)), reasons


def _synthetic_dataset(n=320):
    """بيانات تدريب اصطناعية مبنية على قواعد الخبراء لتغذية النموذج."""
    rng = random.Random(42)
    x_rows = []
    y_labels = []
    quotas = {'ANNUAL': 30, 'SICK': 15, 'EMERGENCY': 15, 'UNPAID': 0}
    for _ in range(n):
        requested_days = rng.randint(1, 30)
        leave_type = rng.choice(['ANNUAL', 'SICK', 'EMERGENCY', 'UNPAID'])
        remaining = rng.randint(0, max(quotas[leave_type], 1))
        is_peak = rng.random() < 0.3
        notice_days = rng.randint(-5, 45)
        dept_conflicts = rng.randint(0, 6)

        balance_ratio = remaining / max(requested_days, 1)
        x_rows.append([
            requested_days,
            round(balance_ratio, 3),
            dept_conflicts,
            int(is_peak),
            notice_days,
            int(leave_type == 'SICK'),
            int(leave_type == 'EMERGENCY'),
            int(leave_type == 'UNPAID'),
        ])
        score, _ = _analyse_features(
            requested_days, remaining, dept_conflicts, is_peak, notice_days, leave_type
        )
        y_labels.append(1 if score >= 50 else 0)
    return x_rows, y_labels


def _load_or_build_model():
    global _model
    if _model is not None:
        return _model
    if not SKLEARN_AVAILABLE:
        return None
    try:
        if os.path.exists(_CACHE_PATH):
            _model = joblib.load(_CACHE_PATH)
            return _model
        x_rows, y_labels = _synthetic_dataset()
        clf = RandomForestClassifier(n_estimators=150, max_depth=8, random_state=42, n_jobs=1)
        clf.fit(x_rows, y_labels)
        try:
            joblib.dump(clf, _CACHE_PATH)
        except Exception:
            pass
        _model = clf
    except Exception:
        _model = None
    return _model


def _ml_probability(requested_days, balance_ratio, dept_conflicts, is_peak, notice_days, leave_type):
    model = _load_or_build_model()
    if model is None:
        return None
    try:
        features = [[
            requested_days,
            round(balance_ratio, 3),
            dept_conflicts,
            int(is_peak),
            notice_days,
            int(leave_type == 'SICK'),
            int(leave_type == 'EMERGENCY'),
            int(leave_type == 'UNPAID'),
        ]]
        proba = model.predict_proba(features)[0]
        if len(proba) == 2:
            return round(proba[1] * 100)
    except Exception:
        return None
    return None


def _verdict(probability):
    if probability >= 70:
        return 'APPROVED', 'الطلب مرشح بشدة للموافقة — لا يتعارض مع مصلحة العمل وفق المعطيات الحالية.'
    if probability >= 45:
        return 'REVIEW', 'الطلب يحتاج إلى مراجعة يدوية من الإدارة — توجد عوامل تستوجب التدقيق قبل القرار.'
    return 'REJECTED', 'الطلب مرشح للرفض — يُنصح بتعديل الفترة أو إعادة النظر في مدة الطلب.'


def predict_leave_approval(*, requested_days, remaining_balance, dept_conflicts, is_peak, notice_days, leave_type='ANNUAL'):
    """
    توليد تحليل ذكي لطلب إجازة.

    المتغيرات: مدة الطلب بالأيام، الرصيد المتبقي، عدد المتعطلين في القسم،
    هل الفترة ضمن الذروة، عدد أيام الإشعار المسبق، ونوع الإجازة.
    يعيد قاموساً بقرار/اختبار، نسبة الثقة، توصية عربية، وقائمة أسباب.
    """
    score, reasons = _analyse_features(
        requested_days, remaining_balance, dept_conflicts, is_peak, notice_days, leave_type
    )

    balance_ratio = remaining_balance / max(requested_days, 1)
    probability = _ml_probability(
        requested_days, balance_ratio, dept_conflicts, is_peak, notice_days, leave_type
    )
    engine = 'ml'
    if probability is None:
        probability = score
        engine = 'rules'
    probability = max(0, min(100, int(probability)))

    verdict, recommendation = _verdict(probability)
    return {
        'probability': probability,
        'verdict': verdict,
        'recommendation': recommendation,
        'reasons': reasons,
        'model': engine,
    }