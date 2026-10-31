"""
apps/accounting/services/chart_of_accounts.py
خدمة التوليد والتهيئة التلقائية لدليل الحسابات الشجري الافتراضي للمدرسة.
يوفر دليلاً محاسبياً مدرسياً متكاملاً وفق المعايير المالية العربية للقيد المزدوج.
"""
from __future__ import annotations

from django.db import transaction

from apps.accounting.models import Account
from apps.tenants.models import School

DEFAULT_ACCOUNTS: list[tuple[str, str, str, str | None, bool]] = [
    # (code, name, account_type, parent_code, is_leaf)
    # ---------------- 1. الأصول (Assets) ----------------
    ("1", "الأصول", Account.AccountType.ASSET, None, False),
    ("11", "الأصول المتداولة", Account.AccountType.ASSET, "1", False),
    ("1101", "الصندوق الرئيسي / الخزينة", Account.AccountType.ASSET, "11", True),
    ("1102", "الحسابات البنكية الجارية", Account.AccountType.ASSET, "11", True),
    ("1103", "أجهزة نقاط البيع (POS) وشبكة مدى", Account.AccountType.ASSET, "11", True),
    ("1104", "ذمم الطلاب وأولياء الأمور (الرسوم المستحقة)", Account.AccountType.ASSET, "11", True),
    ("1105", "سلف وعهد الموظفين المعلقة", Account.AccountType.ASSET, "11", True),
    ("1106", "مخزون الكتب والقرطاسية والزي", Account.AccountType.ASSET, "11", True),
    
    ("12", "الأصول الثابتة", Account.AccountType.ASSET, "1", False),
    ("1201", "الأراضي والمباني المدرسية", Account.AccountType.ASSET, "12", True),
    ("1202", "حافلات ومركبات النقل المدرسي", Account.AccountType.ASSET, "12", True),
    ("1203", "أجهزة الحاسوب وتقنية المعلومات", Account.AccountType.ASSET, "12", True),
    ("1204", "تجهيزات ومختبرات العلوم", Account.AccountType.ASSET, "12", True),
    ("1205", "الأثاث والمفروشات المدرسية", Account.AccountType.ASSET, "12", True),
    ("1209", "مجمع الإهلاك المتراكم للأصول الثابتة", Account.AccountType.ASSET, "12", True),

    # ---------------- 2. الالتزامات (Liabilities) ----------------
    ("2", "الالتزامات والخصوم", Account.AccountType.LIABILITY, None, False),
    ("21", "الالتزامات المتداولة", Account.AccountType.LIABILITY, "2", False),
    ("2101", "ذمم الموردين والشركات الدائنة", Account.AccountType.LIABILITY, "21", True),
    ("2102", "أمانات ورسوم مقبوضة مقدماً", Account.AccountType.LIABILITY, "21", True),
    ("2103", "رواتب وأجور الموظفين المستحقة", Account.AccountType.LIABILITY, "21", True),
    ("2104", "مستحقات التأمينات الاجتماعية والتقاعد", Account.AccountType.LIABILITY, "21", True),
    ("2105", "مستحقات ضريبة القيمة المضافة", Account.AccountType.LIABILITY, "21", True),

    # ---------------- 3. حقوق الملكية (Equity) ----------------
    ("3", "حقوق الملكية", Account.AccountType.EQUITY, None, False),
    ("3101", "رأس مال المؤسسة التعليمية", Account.AccountType.EQUITY, "3", True),
    ("3102", "الأرباح والخسائر المرحلة (المدورة)", Account.AccountType.EQUITY, "3", True),
    ("3103", "جاري المالك / الشركاء", Account.AccountType.EQUITY, "3", True),

    # ---------------- 4. الإيرادات (Revenues) ----------------
    ("4", "الإيرادات", Account.AccountType.REVENUE, None, False),
    ("41", "الإيرادات التعليمية والتشغيلية", Account.AccountType.REVENUE, "4", False),
    ("4101", "إيرادات الرسوم الدراسية", Account.AccountType.REVENUE, "41", True),
    ("4102", "إيرادات رسوم التسجيل والقبول", Account.AccountType.REVENUE, "41", True),
    ("4103", "إيرادات النقل المدرسي", Account.AccountType.REVENUE, "41", True),
    ("4104", "إيرادات بيع الكتب والمذكرات المدرسية", Account.AccountType.REVENUE, "41", True),
    ("4105", "إيرادات الزي المدرسي الرسمي", Account.AccountType.REVENUE, "41", True),
    ("4106", "إيرادات الأنشطة والرحلات الطلابية", Account.AccountType.REVENUE, "41", True),
    ("4107", "إيرادات إيجارات المقاصف والمرافق المدرسية", Account.AccountType.REVENUE, "41", True),
    ("4108", "إيرادات متنوعة وتبرعات", Account.AccountType.REVENUE, "41", True),
    ("42", "إيرادات أخرى وجزاءات", Account.AccountType.REVENUE, "4", False),
    ("4201", "إيرادات جزاءات واستقطاعات غياب الموظفين", Account.AccountType.REVENUE, "42", True),

    # ---------------- 5. المصروفات (Expenses) ----------------
    ("5", "المصروفات", Account.AccountType.EXPENSE, None, False),
    ("51", "تكاليف الرواتب ومزايا الموظفين", Account.AccountType.EXPENSE, "5", False),
    ("5101", "رواتب المعلمين والكادر التدريسي", Account.AccountType.EXPENSE, "51", True),
    ("5102", "رواتب الإداريين والمشرفين", Account.AccountType.EXPENSE, "51", True),
    ("5103", "بدلات سكن ومواصلات للموظفين", Account.AccountType.EXPENSE, "51", True),
    ("5104", "مكافآت وحوافز أداء", Account.AccountType.EXPENSE, "51", True),
    ("5105", "مكافأة نهاية الخدمة والتعويضات", Account.AccountType.EXPENSE, "51", True),
    
    ("52", "المصروفات التشغيلية والإدارية", Account.AccountType.EXPENSE, "5", False),
    ("5201", "إيجار مباني المدارس ومرافقها", Account.AccountType.EXPENSE, "52", True),
    ("5202", "فواتير الكهرباء والمياه والطاقة", Account.AccountType.EXPENSE, "52", True),
    ("5203", "خدمات الاتصالات والإنترنت والبرمجيات", Account.AccountType.EXPENSE, "52", True),
    ("5204", "الصيانة والترميم والنظافة", Account.AccountType.EXPENSE, "52", True),
    ("5205", "وقود وصيانة حافلات النقل المدرسي", Account.AccountType.EXPENSE, "52", True),
    ("5206", "الدعاية والإعلان والتسويق واستقطاب الطلاب", Account.AccountType.EXPENSE, "52", True),
    ("5207", "قرطاسية ومطبوعات ومستلزمات مدرسية", Account.AccountType.EXPENSE, "52", True),
    ("5208", "الضيافة والاحتفالات وتكريم المتفوقين", Account.AccountType.EXPENSE, "52", True),
    ("5209", "مصروفات الإهلاك السنوي للأصول", Account.AccountType.EXPENSE, "52", True),
]


def seed_default_chart_of_accounts(school: School) -> int:
    """
    توليد شجرة الحسابات الافتراضية الشاملة لمدرسة محددة داخل معاملة ذرية.
    تتجنب التكرار إذا كانت الحسابات مولدة مسبقاً.
    """
    created_count = 0
    accounts_by_code = {}

    # Preload existing accounts for this school
    existing = {acc.code: acc for acc in Account.objects.filter(school=school, is_archived=False)}
    accounts_by_code.update(existing)

    with transaction.atomic():
        for code, name, acc_type, parent_code, is_leaf in DEFAULT_ACCOUNTS:
            if code in accounts_by_code:
                continue

            parent_acc = accounts_by_code.get(parent_code) if parent_code else None

            acc = Account.objects.create(
                school=school,
                code=code,
                name=name,
                account_type=acc_type,
                parent=parent_acc,
                is_leaf=is_leaf,
            )
            accounts_by_code[code] = acc
            created_count += 1

    return created_count
