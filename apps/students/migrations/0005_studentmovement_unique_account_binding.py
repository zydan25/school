# Generated for student identity uniqueness and append-only lifecycle history.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


def reject_duplicate_student_account_links(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    duplicates = list(
        Student.objects.using(schema_editor.connection.alias)
        .filter(user__isnull=False, is_archived=False)
        .values("school_id", "user_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)[:10]
    )
    if duplicates:
        raise RuntimeError(
            "Cannot enforce one active student profile per school/account; "
            "resolve duplicate student user links before applying this migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_device_sessions_phone_challenges"),
        ("academics", "0003_section_floor_wing_section_supervisor_user"),
        ("students", "0004_studentenrollment"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            reject_duplicate_student_account_links,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="student",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_archived", False), ("user__isnull", False)),
                fields=("school", "user"),
                name="students_student_school_user_uniq",
            ),
        ),
        migrations.CreateModel(
            name="StudentMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("movement_type", models.CharField(choices=[("admitted", "قبول وتسجيل"), ("promoted", "ترفيع"), ("retained", "إعادة قيد"), ("transferred", "نقل داخلي"), ("graduated", "تخرج"), ("withdrawn", "انسحاب")], max_length=20, verbose_name="نوع الحركة")),
                ("effective_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ سريان الحركة")),
                ("reason", models.TextField(blank=True, verbose_name="سبب الحركة وملاحظاتها")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("next_academic_year", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="academics.academicyear")),
                ("next_grade_level", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="academics.gradelevel")),
                ("next_section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="academics.section")),
                ("previous_academic_year", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="academics.academicyear")),
                ("previous_grade_level", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="academics.gradelevel")),
                ("previous_section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="academics.section")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_student_movements", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="students.student", verbose_name="الطالب")),
            ],
            options={
                "verbose_name": "حركة طالب",
                "verbose_name_plural": "سجل حركات الطلاب",
                "ordering": ["-effective_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="studentmovement",
            index=models.Index(fields=["school", "student", "effective_date"], name="studmov_school_student_idx"),
        ),
        migrations.AddIndex(
            model_name="studentmovement",
            index=models.Index(fields=["school", "movement_type", "effective_date"], name="studmov_school_type_date_idx"),
        ),
    ]
