# Generated for secure authentication sessions and phone OTP workflows.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("token_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("device_id", models.CharField(max_length=128)),
                ("device_name", models.CharField(blank=True, max_length=120)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="device_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "جلسة جهاز",
                "verbose_name_plural": "جلسات الأجهزة",
            },
        ),
        migrations.CreateModel(
            name="PhoneVerificationChallenge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("phone", models.CharField(db_index=True, max_length=20)),
                ("purpose", models.CharField(choices=[("verify_phone", "توثيق رقم الهاتف"), ("password_reset", "استعادة كلمة المرور")], db_index=True, max_length=20)),
                ("code_digest", models.CharField(editable=False, max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("request_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="phone_verification_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "طلب رمز تحقق",
                "verbose_name_plural": "طلبات رموز التحقق",
            },
        ),
        migrations.AlterField(
            model_name="schoolinvitation",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="البريد المدعو"),
        ),
        migrations.AddIndex(
            model_name="devicesession",
            index=models.Index(fields=["user", "revoked_at", "expires_at"], name="accounts_de_user_id_2ae6bf_idx"),
        ),
        migrations.AddIndex(
            model_name="devicesession",
            index=models.Index(fields=["user", "device_id", "revoked_at"], name="accounts_de_user_id_4db35d_idx"),
        ),
        migrations.AddIndex(
            model_name="phoneverificationchallenge",
            index=models.Index(fields=["user", "purpose", "created_at"], name="accounts_ph_user_id_34c2a0_idx"),
        ),
        migrations.AddIndex(
            model_name="phoneverificationchallenge",
            index=models.Index(fields=["phone", "purpose", "created_at"], name="accounts_ph_phone__44ac93_idx"),
        ),
    ]
