import uuid
from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def seed_legacy_warehouse_balances(apps, schema_editor):
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    WarehouseStock = apps.get_model("inventory", "WarehouseStock")
    StockMovement = apps.get_model("inventory", "StockMovement")
    alias = schema_editor.connection.alias

    for item in InventoryItem.objects.using(alias).select_related("warehouse").iterator():
        WarehouseStock.objects.using(alias).get_or_create(
            school_id=item.school_id,
            item_id=item.pk,
            warehouse_id=item.warehouse_id,
            defaults={
                "branch_id": item.warehouse.branch_id,
                "quantity": item.current_stock,
                "average_unit_cost": item.unit_cost,
            },
        )

    for movement in StockMovement.objects.using(alias).select_related("item").iterator():
        StockMovement.objects.using(alias).filter(pk=movement.pk).update(
            warehouse_id=movement.item.warehouse_id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_vendorinvoice_inventory_vendor_invoice_num_uniq"),
        ("accounting", "0007_stage8_treasury_defaults"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WarehouseStock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("quantity", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="الرصيد المتاح")),
                ("average_unit_cost", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14, verbose_name="متوسط تكلفة الوحدة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_balances", to="inventory.inventoryitem", verbose_name="الصنف")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_balances", to="inventory.warehouse", verbose_name="المستودع")),
            ],
            options={"verbose_name": "رصيد صنف في مستودع", "verbose_name_plural": "أرصدة الأصناف بالمستودعات"},
        ),
        migrations.CreateModel(
            name="PurchaseReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("receipt_number", models.CharField(max_length=60, verbose_name="رقم محضر الاستلام")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع التكرار")),
                ("received_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="تاريخ الاستلام")),
                ("payload_hash", models.CharField(max_length=64, verbose_name="بصمة بيانات طلب الاستلام")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات الاستلام")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("purchase_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="inventory.purchaseorder", verbose_name="أمر الشراء")),
                ("received_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_receipts", to=settings.AUTH_USER_MODEL, verbose_name="مستلم التوريد")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={"verbose_name": "محضر استلام مشتريات", "verbose_name_plural": "محاضر استلام المشتريات"},
        ),
        migrations.CreateModel(
            name="WarehouseTransfer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("transfer_number", models.CharField(max_length=60, verbose_name="رقم التحويل")),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="الكمية المحولة")),
                ("unit_cost", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14, verbose_name="تكلفة الوحدة عند التحويل")),
                ("transfer_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ التحويل")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع التكرار")),
                ("status", models.CharField(choices=[("draft", "مسودة"), ("posted", "مرحّل"), ("reversed", "معكوس")], default="draft", max_length=20, verbose_name="الحالة")),
                ("posted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الترحيل")),
                ("reversed_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ العكس")),
                ("notes", models.TextField(verbose_name="سبب التحويل وملاحظاته")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("destination_warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transfers", to="inventory.warehouse", verbose_name="إلى مستودع")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_transfers", to="inventory.inventoryitem", verbose_name="الصنف")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="posted_warehouse_transfers", to=settings.AUTH_USER_MODEL, verbose_name="مرحل التحويل")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("source_warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transfers", to="inventory.warehouse", verbose_name="من مستودع")),
            ],
            options={"verbose_name": "تحويل مخزني", "verbose_name_plural": "تحويلات المستودعات"},
        ),
        migrations.AddField(
            model_name="stockmovement", name="warehouse",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.warehouse", verbose_name="المستودع"),
        ),
        migrations.AddField(
            model_name="stockmovement", name="idempotency_key",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="مفتاح منع التكرار"),
        ),
        migrations.AddField(
            model_name="stockmovement", name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_stock_movements", to=settings.AUTH_USER_MODEL, verbose_name="منشئ الحركة"),
        ),
        migrations.AddField(
            model_name="stockmovement", name="purchase_order_item",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="inventory.purchaseorderitem", verbose_name="بند أمر الشراء"),
        ),
        migrations.AddField(
            model_name="stockmovement", name="purchase_receipt",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.purchasereceipt", verbose_name="محضر الاستلام"),
        ),
        migrations.AddField(
            model_name="stockmovement", name="transfer",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.warehousetransfer", verbose_name="مستند التحويل"),
        ),
        migrations.AddField(
            model_name="stockmovement", name="reversal_of",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reversal", to="inventory.stockmovement", verbose_name="الحركة الأصلية المعكوسة"),
        ),
        migrations.AddField(
            model_name="purchaseorder", name="approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الاعتماد"),
        ),
        migrations.AddField(
            model_name="purchaseorder", name="received_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ اكتمال الاستلام"),
        ),
        migrations.AlterField(
            model_name="purchaseorder", name="status",
            field=models.CharField(choices=[("draft", "مسودة طلب"), ("approved", "أمر شراء معتمد"), ("partially_received", "مستلم جزئياً"), ("received", "مستلم بالكامل في المخزن"), ("cancelled", "ملغى")], default="draft", max_length=24, verbose_name="حالة الطلب"),
        ),
        migrations.AddField(
            model_name="purchaseorderitem", name="received_quantity",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, verbose_name="الكمية المستلمة"),
        ),
        migrations.AlterField(
            model_name="stockmovement", name="unit_cost",
            field=models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14, verbose_name="تكلفة الوحدة"),
        ),
        migrations.AlterField(
            model_name="stockmovement", name="notes",
            field=models.TextField(blank=True, verbose_name="سبب الحركة وملاحظاتها"),
        ),
        migrations.AlterField(
            model_name="stockmovement", name="movement_type",
            field=models.CharField(choices=[("receipt", "توريد وارد (مشتريات)"), ("issue", "صرف"), ("adj_add", "تسوية جردية بالزيادة"), ("adj_sub", "تسوية جردية بالنقص"), ("transfer_in", "استلام تحويل من مستودع"), ("transfer_out", "إرسال تحويل إلى مستودع")], max_length=20, verbose_name="نوع الحركة"),
        ),
        migrations.AddField(
            model_name="vendorinvoice", name="accounting_treatment",
            field=models.CharField(choices=[("inventory", "مخزون"), ("fixed_asset", "أصل ثابت"), ("expense", "مصروف مباشر")], default="inventory", max_length=20, verbose_name="المعالجة المحاسبية"),
        ),
        migrations.AddField(
            model_name="vendorinvoice", name="expense_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_invoices", to="accounting.account", verbose_name="حساب المصروف أو الأصل"),
        ),
        migrations.AddField(
            model_name="vendorinvoice", name="cost_center",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_invoices", to="accounting.costcenter", verbose_name="مركز التكلفة"),
        ),
        migrations.AddField(
            model_name="vendorinvoice", name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_vendor_invoices", to=settings.AUTH_USER_MODEL, verbose_name="معتمد الفاتورة"),
        ),
        migrations.AddField(
            model_name="vendorinvoice", name="approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الاعتماد"),
        ),
        migrations.CreateModel(
            name="VendorInvoicePayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="مبلغ الدفعة")),
                ("idempotency_key", models.CharField(max_length=100, verbose_name="مفتاح منع تكرار الدفعة")),
                ("payment_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ السداد")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="inventory.vendorinvoice", verbose_name="فاتورة المورد")),
                ("journal_entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vendor_invoice_payments", to="accounting.journalentry", verbose_name="القيد المحاسبي")),
                ("payment_voucher", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="vendor_invoice_payment", to="accounting.paymentvoucher", verbose_name="سند الصرف")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendor_invoice_payments", to=settings.AUTH_USER_MODEL, verbose_name="مسجل الدفعة")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={"verbose_name": "دفعة فاتورة مورد", "verbose_name_plural": "دفعات فواتير الموردين"},
        ),
        migrations.RunPython(seed_legacy_warehouse_balances, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="stockmovement", name="warehouse",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.warehouse", verbose_name="المستودع"),
        ),
        migrations.AddConstraint(
            model_name="warehousestock",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "item", "warehouse"), name="inventory_warehouse_stock_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousestock",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gte", 0)), name="inventory_warehouse_stock_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="warehousestock",
            constraint=models.CheckConstraint(condition=models.Q(("average_unit_cost__gte", 0)), name="inventory_warehouse_cost_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="warehousestock",
            index=models.Index(fields=["school", "warehouse", "item"], name="inventory_whstock_scope_idx"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceipt",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="inventory_receipt_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceipt",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "receipt_number"), name="inventory_receipt_number_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousetransfer",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "transfer_number"), name="inventory_transfer_number_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousetransfer",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="inventory_transfer_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="warehousetransfer",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="inventory_transfer_qty_positive"),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False), ("idempotency_key__gt", "")), fields=("school", "idempotency_key"), name="inventory_stock_movement_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="purchaseorderitem",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="inventory_po_item_qty_positive"),
        ),
        migrations.AddConstraint(
            model_name="purchaseorderitem",
            constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="inventory_po_item_price_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchaseorderitem",
            constraint=models.CheckConstraint(condition=models.Q(("received_quantity__gte", 0), ("received_quantity__lte", models.F("quantity"))), name="inventory_po_item_received_range"),
        ),
        migrations.AddConstraint(
            model_name="vendorinvoicepayment",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "idempotency_key"), name="inventory_vendor_payment_idem_uniq"),
        ),
        migrations.AddConstraint(
            model_name="vendorinvoicepayment",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="inventory_vendor_payment_positive"),
        ),
    ]
