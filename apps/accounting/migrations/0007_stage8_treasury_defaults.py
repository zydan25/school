# Stage 8: enforce a single default treasury account per school and kind.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0006_stage8_voucher_idempotency"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="treasuryaccount",
            constraint=models.UniqueConstraint(
                fields=("school", "kind"),
                condition=models.Q(is_archived=False, is_default=True),
                name="acct_treasury_default_uniq",
            ),
        ),
    ]
