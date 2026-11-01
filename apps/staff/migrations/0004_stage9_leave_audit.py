# Stage 9: auditable employee leave decisions.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0003_leavetype_leaverequest_workshift_staffattendance_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="leaverequest",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_leave_requests", to=settings.AUTH_USER_MODEL,
                verbose_name="من راجع الطلب",
            ),
        ),
        migrations.AddField(
            model_name="leaverequest",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ المراجعة"),
        ),
        migrations.AddField(
            model_name="leaverequest",
            name="review_notes",
            field=models.CharField(blank=True, max_length=500, verbose_name="ملاحظات قرار الإجازة"),
        ),
    ]
