from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_stage10_procurement_stock_controls"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="inventoryitem",
            constraint=models.CheckConstraint(condition=models.Q(("current_stock__gte", 0)), name="inventory_item_stock_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="inventoryitem",
            constraint=models.CheckConstraint(condition=models.Q(("unit_cost__gte", 0)), name="inventory_item_cost_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="inventoryitem",
            constraint=models.CheckConstraint(condition=models.Q(("reorder_level__gte", 0)), name="inventory_item_reorder_nonnegative"),
        ),
        migrations.AlterModelOptions(
            name="purchaseorder",
            options={
                "verbose_name": "أمر شراء",
                "verbose_name_plural": "أوامر الشراء والتوريد",
                "permissions": [
                    ("approve_purchaseorder", "Can approve purchase orders"),
                    ("receive_purchaseorder", "Can receive purchase orders"),
                    ("cancel_purchaseorder", "Can cancel purchase orders"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="stockmovement",
            options={
                "verbose_name": "حركة مخزنية",
                "verbose_name_plural": "دفتر حركات المخزون",
                "permissions": [
                    ("reverse_stockmovement", "Can reverse stock movements"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="warehousetransfer",
            options={
                "verbose_name": "تحويل مخزني",
                "verbose_name_plural": "تحويلات المستودعات",
                "permissions": [
                    ("post_warehousetransfer", "Can post warehouse transfers"),
                    ("reverse_warehousetransfer", "Can reverse warehouse transfers"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="vendorinvoice",
            options={
                "verbose_name": "فاتورة مورد",
                "verbose_name_plural": "فواتير الموردين والذمم الدائنة",
                "permissions": [
                    ("approve_vendorinvoice", "Can approve vendor invoices"),
                    ("pay_vendorinvoice", "Can pay vendor invoices"),
                ],
            },
        ),
    ]
