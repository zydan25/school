# Generated for stage 8 treasury and bank reconciliation.
import django.db.models.deletion
import django.utils.timezone
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0002_stage8_fiscal_controls"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TreasuryAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("name", models.CharField(max_length=150, verbose_name="اسم الصندوق أو الحساب البنكي")),
                ("code", models.CharField(max_length=50, verbose_name="الرمز")),
                ("kind", models.CharField(choices=[("cash", "صندوق نقدي"), ("bank", "حساب بنكي")], max_length=10, verbose_name="النوع")),
                ("bank_name", models.CharField(blank=True, max_length=150, verbose_name="اسم البنك")),
                ("bank_account_number", models.CharField(blank=True, max_length=100, verbose_name="رقم الحساب البنكي")),
                ("currency", models.CharField(default="YER", max_length=3, verbose_name="رمز العملة")),
                ("is_default", models.BooleanField(default=False, verbose_name="الحساب الافتراضي لنوعه")),
                ("is_active", models.BooleanField(default=True, verbose_name="نشط")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("account", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="treasury_account", to="accounting.account", verbose_name="حساب الأستاذ المرتبط")),
            ],
            options={"verbose_name": "صندوق / حساب بنكي", "verbose_name_plural": "الصناديق والحسابات البنكية"},
        ),
        migrations.CreateModel(
            name="TreasuryTransfer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("transfer_number", models.CharField(max_length=60, verbose_name="رقم التحويل")),
                ("transfer_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ التحويل")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="مبلغ التحويل")),
                ("description", models.CharField(max_length=255, verbose_name="البيان")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع تكرار التحويل")),
                ("status", models.CharField(choices=[("draft", "مسودة"), ("posted", "مرحل"), ("reversed", "معكوس")], default="draft", max_length=20, verbose_name="الحالة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("source_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transfers", to="accounting.treasuryaccount", verbose_name="من حساب")),
                ("destination_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transfers", to="accounting.treasuryaccount", verbose_name="إلى حساب")),
                ("journal_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="treasury_transfers", to="accounting.journalentry", verbose_name="القيد المحاسبي")),
                ("reversed_by_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reversed_treasury_transfers", to="accounting.journalentry", verbose_name="القيد العكسي")),
            ],
            options={"verbose_name": "تحويل خزينة", "verbose_name_plural": "تحويلات الخزينة"},
        ),
        migrations.CreateModel(
            name="BankReconciliation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("start_date", models.DateField(verbose_name="بداية كشف البنك")),
                ("end_date", models.DateField(verbose_name="نهاية كشف البنك")),
                ("statement_opening_balance", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="رصيد كشف البنك الافتتاحي")),
                ("statement_closing_balance", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="رصيد كشف البنك الختامي")),
                ("book_opening_balance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="رصيد الأستاذ الافتتاحي")),
                ("book_closing_balance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="رصيد الأستاذ الختامي")),
                ("outstanding_ledger_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="حركات الأستاذ غير الظاهرة في الكشف")),
                ("difference", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="فرق المطابقة")),
                ("status", models.CharField(choices=[("draft", "مسودة"), ("reconciled", "مطابق")], default="draft", max_length=20, verbose_name="الحالة")),
                ("reconciled_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ المطابقة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("treasury_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reconciliations", to="accounting.treasuryaccount", verbose_name="الحساب البنكي")),
                ("reconciled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bank_reconciliations", to=settings.AUTH_USER_MODEL, verbose_name="المسؤول عن المطابقة")),
            ],
            options={"verbose_name": "مطابقة كشف بنكي", "verbose_name_plural": "مطابقات كشوف البنوك"},
        ),
        migrations.CreateModel(
            name="BankStatementLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("transaction_date", models.DateField(verbose_name="تاريخ الحركة البنكية")),
                ("external_reference", models.CharField(max_length=120, verbose_name="المرجع البنكي")),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="البيان")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="المبلغ (الإيداع موجب والسحب سالب)")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("reconciliation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="statement_lines", to="accounting.bankreconciliation", verbose_name="محضر المطابقة")),
                ("journal_line", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bank_statement_match", to="accounting.journalentryline", verbose_name="سطر دفتر الأستاذ المطابق")),
            ],
            options={"verbose_name": "حركة كشف بنك", "verbose_name_plural": "حركات كشوف البنوك"},
        ),
        migrations.AddIndex(
            model_name="treasuryaccount",
            index=models.Index(fields=["school", "kind", "is_active"], name="acct_tr_kind_active"),
        ),
        migrations.AddConstraint(
            model_name="treasuryaccount",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "code"), name="acct_treasury_code_uniq"),
        ),
        migrations.AddConstraint(
            model_name="treasurytransfer",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "transfer_number"), name="acct_transfer_num_uniq"),
        ),
        migrations.AddConstraint(
            model_name="treasurytransfer",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="acct_transfer_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="bankreconciliation",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "treasury_account", "start_date", "end_date"), name="acct_bank_recon_range_uniq"),
        ),
        migrations.AddConstraint(
            model_name="bankstatementline",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("reconciliation", "external_reference"), name="acct_bank_stmt_ref_uniq"),
        ),
    ]
