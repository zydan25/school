# Stage 12: route private conversation attachments outside public MEDIA_ROOT.
import apps.core.storage
from django.db import migrations, models
import apps.notifications.models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0006_stage12_school_email_gateway")]
    operations = [
        migrations.AlterField(
            model_name="conversationmessage",
            name="attachment",
            field=models.FileField(
                blank=True,
                storage=apps.core.storage.private_storage,
                upload_to=apps.notifications.models.conversation_attachment_path,
                verbose_name="المرفق الخاص",
            ),
        ),
    ]
