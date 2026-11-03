from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_stage10_stock_ledger_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockmovement",
            name="movement_type",
            field=models.CharField(
                choices=[
                    ("opening", "رصيد افتتاحي"),
                    ("receipt", "توريد وارد (مشتريات)"),
                    ("issue", "صرف"),
                    ("adj_add", "تسوية جردية بالزيادة"),
                    ("adj_sub", "تسوية جردية بالنقص"),
                    ("transfer_in", "استلام تحويل من مستودع"),
                    ("transfer_out", "إرسال تحويل إلى مستودع"),
                ],
                max_length=20,
                verbose_name="نوع الحركة",
            ),
        ),
    ]
