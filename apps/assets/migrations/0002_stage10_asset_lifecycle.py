import uuid
from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0001_initial"),
        ("inventory", "0004_stage10_procurement_stock_controls"),
        ("accounting", "0007_stage8_treasury_defaults"),
        ("tenants", "0001_initial"),
        ("staff", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="assetcategory",
            name="asset_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_categories", to="accounting.account", verbose_name="حساب تكلفة الأصل"),
        ),
        migrations.AddField(
            model_name="assetcategory",
            name="depreciation_expense_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_categories_expense", to="accounting.account", verbose_name="حساب مصروف الإهلاك"),
        ),
        migrations.AddField(
            model_name="assetcategory",
            name="accumulated_depreciation_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_categories_accumulated", to="accounting.account", verbose_name="حساب مجمع الإهلاك"),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="source_vendor_invoice",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="capitalized_assets", to="inventory.vendorinvoice", verbose_name="فاتورة المورد المصدر"),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="acquisition_journal_entry",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="acquired_fixed_assets", to="accounting.journalentry", verbose_name="قيد اقتناء الأصل"),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="disposal_journal_entry",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="disposed_fixed_assets", to="accounting.journalentry", verbose_name="قيد استبعاد الأصل"),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="disposed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ استبعاد الأصل"),
        ),
        migrations.AddField(
            model_name="assetdepreciationentry",
            name="journal_entry",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_depreciation_entries", to="accounting.journalentry", verbose_name="قيد الإهلاك المرحّل"),
        ),
        migrations.AddField(
            model_name="assetdepreciationentry",
            name="posted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ ترحيل الإهلاك"),
        ),
        migrations.AddField(
            model_name="assetdepreciationentry",
            name="posted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="posted_asset_depreciations", to=settings.AUTH_USER_MODEL, verbose_name="مرحل الإهلاك"),
        ),
        migrations.CreateModel(
            name="AssetMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("movement_type", models.CharField(choices=[("transfer", "نقل بين الفروع أو المواقع"), ("custody", "تسليم أو استلام عهدة")], max_length=20, verbose_name="نوع الحركة")),
                ("from_location", models.CharField(blank=True, max_length=150, verbose_name="الموقع السابق")),
                ("to_location", models.CharField(blank=True, max_length=150, verbose_name="الموقع الجديد")),
                ("movement_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ الحركة")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع التكرار")),
                ("reason", models.CharField(max_length=500, verbose_name="سبب النقل أو تغيير العهدة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفة")),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="assets.fixedasset", verbose_name="الأصل")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("from_branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_movements_from", to="tenants.branch", verbose_name="الفرع السابق")),
                ("from_custodian", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_custody_out", to="staff.teacher", verbose_name="أمين العهدة السابق")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="asset_movements_recorded", to=settings.AUTH_USER_MODEL, verbose_name="مسجل الحركة")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("to_branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_movements_to", to="tenants.branch", verbose_name="الفرع الجديد")),
                ("to_custodian", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_custody_in", to="staff.teacher", verbose_name="أمين العهدة الجديد")),
            ],
            options={"verbose_name": "حركة نقل أصل أو عهدة", "verbose_name_plural": "سجل نقل الأصول والعهد"},
        ),
        migrations.CreateModel(
            name="AssetDisposal",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("disposal_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ الاستبعاد")),
                ("proceeds", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="قيمة البيع أو المتحصل")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع التكرار")),
                ("reason", models.CharField(max_length=500, verbose_name="سبب الاستبعاد")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفة")),
                ("asset", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="disposal", to="assets.fixedasset", verbose_name="الأصل المستبعد")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("disposed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="asset_disposals", to=settings.AUTH_USER_MODEL, verbose_name="منفذ الاستبعاد")),
                ("journal_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_disposals", to="accounting.journalentry", verbose_name="قيد الاستبعاد")),
                ("payment_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_disposals", to="accounting.account", verbose_name="حساب تحصيل قيمة البيع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={"verbose_name": "مستند استبعاد أصل", "verbose_name_plural": "مستندات استبعاد الأصول"},
        ),
        migrations.AddConstraint(
            model_name="assetcategory",
            constraint=models.CheckConstraint(condition=models.Q(("annual_depreciation_rate__gte", 0), ("annual_depreciation_rate__lte", 100)), name="assets_category_rate_range"),
        ),
        migrations.AddConstraint(
            model_name="assetcategory",
            constraint=models.CheckConstraint(condition=models.Q(("useful_life_years__gt", 0)), name="assets_category_life_positive"),
        ),
        migrations.AddConstraint(
            model_name="assetmovement",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="assets_movement_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="assetdisposal",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="assets_disposal_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="assetdisposal",
            constraint=models.CheckConstraint(condition=models.Q(("proceeds__gte", 0)), name="assets_disposal_proceeds_nonnegative"),
        ),
    ]
