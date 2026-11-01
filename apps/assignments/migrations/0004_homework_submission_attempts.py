# Generated for phase 6: preserve existing submissions as their first attempt.
import apps.assignments.models
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


def copy_existing_submissions(apps, schema_editor):
    Submission = apps.get_model("assignments", "HomeworkSubmission")
    Attempt = apps.get_model("assignments", "HomeworkSubmissionAttempt")
    alias = schema_editor.connection.alias
    rows = Submission.objects.using(alias).filter(is_archived=False).iterator()
    for row in rows:
        Attempt.objects.using(alias).get_or_create(
            school_id=row.school_id,
            submission_id=row.pk,
            attempt_number=1,
            defaults={
                "branch_id": row.branch_id,
                "submission_text": row.submission_text,
                "attachment": row.attachment.name if row.attachment else "",
                "submitted_at": row.submitted_at,
                "status": "late" if row.status == "late" else "submitted",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("assignments", "0003_initial"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeworkSubmissionAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("attempt_number", models.PositiveSmallIntegerField(verbose_name="رقم المحاولة")),
                ("submission_text", models.TextField(blank=True, verbose_name="نص الإجابة في هذه المحاولة")),
                ("attachment", models.FileField(blank=True, upload_to=apps.assignments.models.homework_attempt_upload_path, verbose_name="مرفق هذه المحاولة")),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="وقت هذه المحاولة")),
                ("status", models.CharField(choices=[("submitted", "تم التسليم"), ("late", "تسليم متأخر")], default="submitted", max_length=20, verbose_name="حالة المحاولة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attempts", to="assignments.homeworksubmission", verbose_name="سجل تسليم الواجب")),
            ],
            options={
                "verbose_name": "محاولة تسليم واجب",
                "verbose_name_plural": "سجل محاولات تسليم الواجبات",
                "ordering": ["attempt_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="homeworksubmissionattempt",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "submission", "attempt_number"), name="assignments_attempt_number_uniq"),
        ),
        migrations.AddIndex(
            model_name="homeworksubmissionattempt",
            index=models.Index(fields=["school", "submission", "submitted_at"], name="asgn_attempt_idx"),
        ),
        migrations.RunPython(copy_existing_submissions, migrations.RunPython.noop),
    ]
