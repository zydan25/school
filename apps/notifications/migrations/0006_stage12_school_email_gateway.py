# Stage 12: per-school SMTP delivery credentials.
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
import apps.core.fields


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_stage12_delivery_worker")]
    operations = [
        migrations.CreateModel(
            name="SchoolEmailGateway",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_active", models.BooleanField(default=False, verbose_name="بوابة البريد مفعلة")),
                ("host", models.CharField(blank=True, max_length=255, verbose_name="خادم SMTP")),
                ("port", models.PositiveSmallIntegerField(default=587, verbose_name="منفذ SMTP")),
                ("username", models.CharField(blank=True, max_length=255, verbose_name="اسم مستخدم SMTP")),
                ("password", apps.core.fields.EncryptedTextField(blank=True, verbose_name="كلمة مرور SMTP")),
                ("from_email", models.EmailField(blank=True, max_length=254, verbose_name="عنوان المرسل")),
                ("use_tls", models.BooleanField(default=True, verbose_name="TLS")),
                ("use_ssl", models.BooleanField(default=False, verbose_name="SSL")),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="email_gateway", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={"verbose_name": "بوابة البريد الإلكتروني للمدرسة", "verbose_name_plural": "بوابات البريد الإلكتروني للمدارس"},
        ),
    ]
