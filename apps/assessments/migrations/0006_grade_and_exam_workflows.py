# Generated for phase 6: workflow state, controlled result publication and proctor roles.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill_legacy_publication(apps, schema_editor):
    GradeBook = apps.get_model("assessments", "GradeBook")
    Submission = apps.get_model("assessments", "StudentOnlineExamSubmission")
    alias = schema_editor.connection.alias
    GradeBook.objects.using(alias).filter(is_published=True).update(
        workflow_status="published",
        published_at=models.F("graded_at"),
    )
    Submission.objects.using(alias).filter(status="graded").update(
        result_published=True,
        result_published_at=models.F("submitted_at"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0005_questionbank_onlineexam_studentonlineexamsubmission_and_more"),
        ("staff", "0001_initial"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="gradebook",
            name="is_published",
            field=models.BooleanField(default=False, verbose_name="منشورة للطالب وولي الأمر"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="workflow_status",
            field=models.CharField(choices=[("draft", "مسودة"), ("submitted", "مرسلة للمراجعة"), ("approved", "معتمدة"), ("published", "منشورة")], db_index=True, default="draft", max_length=20, verbose_name="حالة اعتماد الدرجة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="submitted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_grade_records", to=settings.AUTH_USER_MODEL, verbose_name="مرسل الدرجة للمراجعة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="submitted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="وقت إرسال الدرجة للمراجعة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_grade_records", to=settings.AUTH_USER_MODEL, verbose_name="معتمد الدرجة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="وقت اعتماد الدرجة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="published_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_grade_records", to=settings.AUTH_USER_MODEL, verbose_name="ناشر الدرجة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="وقت نشر الدرجة"),
        ),
        migrations.AddField(
            model_name="gradebook",
            name="revision_reason",
            field=models.CharField(blank=True, max_length=500, verbose_name="سبب إعادة فتح الدرجة"),
        ),
        migrations.AlterField(
            model_name="onlineexam",
            name="is_published",
            field=models.BooleanField(default=False, verbose_name="منشور ومتاح للطلاب في موعده"),
        ),
        migrations.AddField(
            model_name="onlineexam",
            name="published_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_online_exams", to=settings.AUTH_USER_MODEL, verbose_name="ناشر الاختبار"),
        ),
        migrations.AddField(
            model_name="onlineexam",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="وقت نشر الاختبار"),
        ),
        migrations.AddField(
            model_name="onlineexam",
            name="unpublished_reason",
            field=models.CharField(blank=True, max_length=500, verbose_name="سبب إلغاء نشر الاختبار"),
        ),
        migrations.AddField(
            model_name="studentonlineexamsubmission",
            name="result_published",
            field=models.BooleanField(db_index=True, default=False, verbose_name="النتيجة منشورة للطالب"),
        ),
        migrations.AddField(
            model_name="studentonlineexamsubmission",
            name="result_published_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="وقت نشر النتيجة"),
        ),
        migrations.AddField(
            model_name="studentonlineexamsubmission",
            name="result_published_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_exam_results", to=settings.AUTH_USER_MODEL, verbose_name="ناشر النتيجة"),
        ),
        migrations.AddField(
            model_name="studentonlineexamsubmission",
            name="result_revision_reason",
            field=models.CharField(blank=True, max_length=500, verbose_name="سبب إعادة فتح النتيجة"),
        ),
        migrations.CreateModel(
            name="ExamCommitteeProctor",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("duty", models.CharField(choices=[("chief", "رئيس لجنة"), ("proctor", "مراقب")], default="proctor", max_length=20, verbose_name="المهمة")),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="وقت التكليف")),
                ("notes", models.CharField(blank=True, max_length=500, verbose_name="ملاحظات التكليف")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_exam_proctors", to=settings.AUTH_USER_MODEL, verbose_name="من كلف المراقب")),
                ("committee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="proctor_assignments", to="assessments.examcommittee", verbose_name="اللجنة")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_committee_assignments", to="staff.teacher", verbose_name="المعلم المكلف")),
            ],
            options={
                "verbose_name": "تكليف مراقب لجنة",
                "verbose_name_plural": "تكليفات مراقبي اللجان",
            },
        ),
        migrations.AddConstraint(
            model_name="examcommitteeproctor",
            constraint=models.UniqueConstraint(condition=models.Q(("is_archived", False)), fields=("school", "committee", "teacher"), name="assessments_committee_proctor_uniq"),
        ),
        migrations.AddIndex(
            model_name="examcommitteeproctor",
            index=models.Index(fields=["school", "teacher", "duty"], name="assessments_school_proctor_idx"),
        ),
        migrations.RunPython(backfill_legacy_publication, migrations.RunPython.noop),
    ]
