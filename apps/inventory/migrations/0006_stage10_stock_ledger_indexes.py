from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_stage10_integrity_and_permissions"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="stockmovement",
            name="inventory_stock_movement_idem_uniq",
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["school", "warehouse", "date"], name="inventory_stock_wh_date_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["school", "item", "date"], name="inventory_stock_item_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key__gt", ""), ("is_archived", False)),
                fields=("school", "idempotency_key"),
                name="inventory_stock_movement_idem_uniq",
            ),
        ),
    ]
