from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0003_stage8_treasury"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentvoucher",
            name="idempotency_key",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="مفتاح منع تكرار السند"),
        ),
        migrations.AddField(
            model_name="receiptvoucher",
            name="idempotency_key",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="مفتاح منع تكرار السند"),
        ),
        migrations.AddConstraint(
            model_name="paymentvoucher",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key__gt", ""), ("is_archived", False)),
                fields=("school", "idempotency_key"),
                name="acct_payment_idem_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="receiptvoucher",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key__gt", ""), ("is_archived", False)),
                fields=("school", "idempotency_key"),
                name="acct_receipt_idem_uniq",
            ),
        ),
    ]
