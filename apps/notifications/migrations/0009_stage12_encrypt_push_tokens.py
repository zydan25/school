# Stage 12: encrypt device push tokens and index them by a non-reversible fingerprint.
import hashlib
from django.db import migrations, models
import apps.core.fields


def populate_push_token_fingerprints(apps, schema_editor):
    PushDevice = apps.get_model("notifications", "PushDevice")
    for device in PushDevice.objects.all().iterator():
        device.push_token_fingerprint = hashlib.sha256(device.push_token.encode("utf-8")).hexdigest()
        device.save(update_fields=["push_token_fingerprint"])


class Migration(migrations.Migration):
    dependencies = [("notifications", "0008_stage12_delivery_receipts_and_rate_limits")]
    operations = [
        migrations.AddField(
            model_name="pushdevice",
            name="push_token_fingerprint",
            field=models.CharField(blank=True, default="", editable=False, max_length=64, verbose_name="بصمة رمز Push"),
        ),
        migrations.RunPython(populate_push_token_fingerprints, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pushdevice",
            name="push_token_fingerprint",
            field=models.CharField(editable=False, max_length=64, unique=True, verbose_name="بصمة رمز Push"),
        ),
        migrations.AlterField(
            model_name="pushdevice",
            name="push_token",
            field=apps.core.fields.EncryptedTextField(verbose_name="رمز Push مشفر"),
        ),
    ]
