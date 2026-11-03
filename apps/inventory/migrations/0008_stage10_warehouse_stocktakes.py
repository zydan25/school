import uuid
from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_stage10_opening_stock_movement"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WarehouseStocktake",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("stocktake_number", models.CharField(max_length=60, verbose_name="رقم محضر الجرد")),
                ("count_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ الجرد")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع تكرار الجرد")),
                ("status", models.CharField(choices=[("counting", "قيد الجرد"), ("posted", "معتمد ومرحّل"), ("cancelled", "ملغى")], default="counting", max_length=20, verbose_name="حالة الجرد")),
                ("posted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ اعتماد الجرد")),
                ("cancelled_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ إلغاء الجرد")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات الجرد")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("cancelled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cancelled_inventory_stocktakes", to=settings.AUTH_USER_MODEL, verbose_name="ملغي الجرد")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_inventory_stocktakes", to=settings.AUTH_USER_MODEL, verbose_name="منشئ الجرد")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="posted_inventory_stocktakes", to=settings.AUTH_USER_MODEL, verbose_name="معتمد الجرد")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stocktakes", to="inventory.warehouse", verbose_name="المستودع")),
            ],
            options={
                "verbose_name": "محضر جرد مخزني",
                "verbose_name_plural": "محاضر الجرد المخزني",
                "permissions": [
                    ("count_warehousestocktake", "Can record warehouse stock counts"),
                    ("post_warehousestocktake", "Can post warehouse stocktakes"),
                    ("cancel_warehousestocktake", "Can cancel warehouse stocktakes"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WarehouseStocktakeLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("system_quantity", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="رصيد النظام عند بدء الجرد")),
                ("counted_quantity", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name="الكمية الفعلية المعدودة")),
                ("unit_cost", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14, verbose_name="متوسط تكلفة الوحدة وقت الجرد")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stocktake_lines", to="inventory.inventoryitem", verbose_name="الصنف")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("stocktake", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="inventory.warehousestocktake", verbose_name="محضر الجرد")),
            ],
            options={
                "verbose_name": "بند محضر جرد",
                "verbose_name_plural": "بنود محاضر الجرد",
            },
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="stocktake_line",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movement", to="inventory.warehousestocktakeline", verbose_name="بند الجرد المصدر"),
        ),
        migrations.AddConstraint(
            model_name="warehousestocktake",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "stocktake_number"), name="inventory_stocktake_number_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousestocktake",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="inventory_stocktake_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousestocktake",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False), ("status", "counting")), fields=("school", "warehouse"), name="inventory_one_active_stocktake_uniq"),
        ),
        migrations.AddIndex(
            model_name="warehousestocktake",
            index=models.Index(fields=["school", "warehouse", "status"], name="inventory_stocktake_scope_idx"),
        ),
        migrations.AddConstraint(
            model_name="warehousestocktakeline",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "stocktake", "item"), name="inventory_stocktake_item_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousestocktakeline",
            constraint=models.CheckConstraint(condition=models.Q(("system_quantity__gte", 0)), name="inventory_stocktake_system_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="warehousestocktakeline",
            constraint=models.CheckConstraint(condition=models.Q(("counted_quantity__isnull", True), ("counted_quantity__gte", 0), _connector="OR"), name="inventory_stocktake_count_nonnegative"),
        ),
    ]
