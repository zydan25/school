# Stage 12: reliable delivery, encrypted gateway secrets and delivery audit.
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
import apps.core.fields


def encrypt_existing_gateway_secrets(apps, schema_editor):
    Gateway = apps.get_model("notifications", "SchoolMessagingGateway")
    for gateway in Gateway.objects.all().iterator():
        gateway.save(update_fields=["auth_token", "webhook_verify_token"])


class Migration(migrations.Migration):
    dependencies = [("notifications", "0004_pushdevice_schoolconversation")]
    operations = [
        migrations.AlterField(
            model_name="schoolmessaginggateway", name="auth_token",
            field=apps.core.fields.EncryptedTextField(blank=True, verbose_name="مفتاح المصادقة والتوكن (API Key / Token)"),
        ),
        migrations.AlterField(
            model_name="schoolmessaginggateway", name="webhook_verify_token",
            field=apps.core.fields.EncryptedTextField(blank=True, verbose_name="المفتاح السري للتحقق من الرسائل الواردة (Webhook Secret)"),
        ),
        migrations.AlterField(
            model_name="inboundwebhookmessage", name="processed",
            field=models.BooleanField(default=False, verbose_name="تمت المعالجة"),
        ),
        migrations.AddField(
            model_name="outboxevent", name="locked_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="وقت قفل العامل"),
        ),
        migrations.AddField(
            model_name="inboundwebhookmessage", name="last_error",
            field=models.CharField(blank=True, max_length=500, verbose_name="آخر خطأ معالجة"),
        ),
        migrations.CreateModel(
            name="NotificationDeliveryAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("attempt_number", models.PositiveSmallIntegerField(verbose_name="رقم المحاولة")),
                ("destination_fingerprint", models.CharField(blank=True, max_length=64, verbose_name="بصمة الوجهة")),
                ("provider", models.CharField(blank=True, max_length=40, verbose_name="المزود")),
                ("status", models.CharField(choices=[("succeeded", "قبلها المزود"), ("failed", "فشلت المحاولة")], max_length=12, verbose_name="الحالة")),
                ("provider_reference", models.CharField(blank=True, max_length=160, verbose_name="مرجع المزود")),
                ("response_code", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="رمز استجابة HTTP")),
                ("error_code", models.CharField(blank=True, max_length=80, verbose_name="رمز الخطأ")),
                ("error_message", models.CharField(blank=True, max_length=500, verbose_name="وصف الخطأ")),
                ("attempted_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="وقت المحاولة")),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_attempts", to="notifications.notification", verbose_name="الإشعار")),
            ],
            options={"verbose_name": "محاولة تسليم إشعار", "verbose_name_plural": "محاولات تسليم الإشعارات", "ordering": ["-attempted_at"], "indexes": [models.Index(fields=["notification", "attempted_at"], name="ntf_attempt_notif_time")]},
        ),
        migrations.RunPython(encrypt_existing_gateway_secrets, migrations.RunPython.noop),
    ]
