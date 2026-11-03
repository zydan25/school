# Stage 12: per-school AI budget, quota and usage audit.
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("copilot", "0002_initial"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="SchoolAIUsagePolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("enabled", models.BooleanField(default=False, verbose_name="تفعيل الذكاء الاصطناعي")),
                ("daily_request_limit", models.PositiveIntegerField(default=50, verbose_name="الحد اليومي للطلبات")),
                ("daily_token_limit", models.PositiveIntegerField(default=50000, verbose_name="الحد اليومي للتوكنز")),
                ("monthly_budget_amount", models.DecimalField(decimal_places=4, default=0, max_digits=14, verbose_name="الميزانية الشهرية")),
                ("input_cost_per_1k_tokens", models.DecimalField(decimal_places=8, default=0, max_digits=14, verbose_name="تكلفة 1000 توكن إدخال")),
                ("output_cost_per_1k_tokens", models.DecimalField(decimal_places=8, default=0, max_digits=14, verbose_name="تكلفة 1000 توكن إخراج")),
                ("currency", models.CharField(default="USD", max_length=3, verbose_name="العملة")),
                ("max_output_tokens", models.PositiveIntegerField(default=4000, verbose_name="أقصى توكنز إخراج للطلب")),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ai_usage_policy", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={"verbose_name": "سياسة استخدام الذكاء الاصطناعي", "verbose_name_plural": "سياسات استخدام الذكاء الاصطناعي"},
        ),
        migrations.CreateModel(
            name="AIUsageRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("tool", models.CharField(db_index=True, max_length=80, verbose_name="الأداة")),
                ("model_name", models.CharField(max_length=100, verbose_name="النموذج")),
                ("source_refs", models.JSONField(blank=True, default=dict, verbose_name="مراجع مصادر البيانات")),
                ("input_tokens", models.PositiveIntegerField(default=0, verbose_name="توكنز الإدخال المقدرة")),
                ("output_tokens", models.PositiveIntegerField(default=0, verbose_name="توكنز الإخراج المقدرة")),
                ("estimated_cost", models.DecimalField(decimal_places=8, default=0, max_digits=16, verbose_name="التكلفة المقدرة")),
                ("currency", models.CharField(default="USD", max_length=3, verbose_name="العملة")),
                ("status", models.CharField(choices=[("started", "قيد التنفيذ"), ("succeeded", "ناجح"), ("failed", "فشل")], db_index=True, default="started", max_length=12, verbose_name="الحالة")),
                ("failure_code", models.CharField(blank=True, max_length=80, verbose_name="رمز الفشل")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت الاكتمال")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ai_usage_records", to="tenants.school")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ai_usage_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "سجل استهلاك الذكاء الاصطناعي", "verbose_name_plural": "سجلات استهلاك الذكاء الاصطناعي", "indexes": [models.Index(fields=["school", "created_at"], name="copilot_ai_school_date"), models.Index(fields=["school", "user", "created_at"], name="copilot_ai_user_date")]},
        ),
    ]
