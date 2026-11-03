# Stage 12: cancel pending notices, provider delivery receipts and rate limits.
import uuid
import django.utils.timezone
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0007_stage12_private_conversation_attachments")]
    operations = [
        migrations.AlterField(
            model_name="outboxevent",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "بانتظار المعالجة"),
                    ("processing", "قيد المعالجة"),
                    ("processed", "تمت المعالجة"),
                    ("failed", "فشلت"),
                    ("cancelled", "ملغاة"),
                ],
                db_index=True, default="pending", max_length=12, verbose_name="الحالة",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "في قائمة الإرسال"),
                    ("sent", "مرسلة"),
                    ("delivered", "تم التسليم"),
                    ("failed", "فشل الإرسال"),
                    ("read", "مقروءة"),
                    ("cancelled", "ملغاة"),
                ],
                db_index=True, default="queued", max_length=12, verbose_name="حالة الإرسال",
            ),
        ),
        migrations.AddField(
            model_name="schoolmessaginggateway", name="rate_limit_per_minute",
            field=models.PositiveSmallIntegerField(default=60, verbose_name="حد الإرسال في الدقيقة"),
        ),
        migrations.AddField(
            model_name="schoolmessaginggateway", name="rate_limit_window_started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="بداية نافذة الإرسال"),
        ),
        migrations.AddField(
            model_name="schoolmessaginggateway", name="rate_limit_window_count",
            field=models.PositiveIntegerField(default=0, verbose_name="عدد الرسائل في النافذة"),
        ),
        migrations.AddField(
            model_name="schoolemailgateway", name="rate_limit_per_minute",
            field=models.PositiveSmallIntegerField(default=60, verbose_name="حد الإرسال في الدقيقة"),
        ),
        migrations.AddField(
            model_name="schoolemailgateway", name="rate_limit_window_started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="بداية نافذة الإرسال"),
        ),
        migrations.AddField(
            model_name="schoolemailgateway", name="rate_limit_window_count",
            field=models.PositiveIntegerField(default=0, verbose_name="عدد الرسائل في النافذة"),
        ),
        migrations.CreateModel(
            name="NotificationDeliveryReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("provider", models.CharField(max_length=40, verbose_name="المزود")),
                ("provider_reference", models.CharField(max_length=160, verbose_name="مرجع المزود")),
                ("status", models.CharField(choices=[("sent", "قبل المزود الإرسال"), ("delivered", "تم التسليم"), ("read", "قرأ المستلم الرسالة"), ("failed", "فشل التسليم")], max_length=12, verbose_name="حالة التسليم")),
                ("error_code", models.CharField(blank=True, max_length=80, verbose_name="رمز فشل المزود")),
                ("received_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="وقت استلام الإيصال")),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_receipts", to="notifications.notification", verbose_name="الإشعار")),
            ],
            options={
                "verbose_name": "إيصال تسليم إشعار",
                "verbose_name_plural": "إيصالات تسليم الإشعارات",
                "ordering": ["-received_at"],
                "constraints": [models.UniqueConstraint(fields=("notification", "provider_reference", "status"), name="ntf_receipt_status_uniq")],
                "indexes": [models.Index(fields=["provider_reference", "received_at"], name="ntf_receipt_provider_ref")],
            },
        ),
    ]
