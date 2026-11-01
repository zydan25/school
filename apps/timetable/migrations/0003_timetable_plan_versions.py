from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0004_branch_scoped_academic_structure"),
        ("timetable", "0002_schoolbellschedule_scheduleperiodtemplate_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TimetablePlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("name", models.CharField(max_length=150)),
                ("version", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(choices=[("draft", "مسودة"), ("in_review", "قيد المراجعة"), ("approved", "معتمدة للنشر"), ("published", "منشورة ونافذة"), ("retired", "منتهية")], db_index=True, default="draft", max_length=20)),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_current", models.BooleanField(db_index=True, default=False)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("academic_term", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="timetable_plans", to="academics.academicterm")),
                ("academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_plans", to="academics.academicyear")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_timetable_plans", to=settings.AUTH_USER_MODEL)),
                ("based_on", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="derived_versions", to="timetable.timetableplan")),
                ("bell_schedule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="timetable_plans", to="timetable.schoolbellschedule")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_timetable_plans", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_timetable_plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-academic_year__starts_on", "-version"]},
        ),
        migrations.AddField(
            model_name="classschedule",
            name="timetable_plan",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="class_schedules", to="timetable.timetableplan", verbose_name="نسخة الجدول المعتمدة"),
        ),
        migrations.RemoveConstraint("schoolbellschedule", "timetable_bellsched_school_name_uniq"),
        migrations.AddConstraint("schoolbellschedule", models.UniqueConstraint(fields=("school", "academic_year", "name"), condition=Q(is_archived=False, branch__isnull=True), name="tt_bell_name_global_uq")),
        migrations.AddConstraint("schoolbellschedule", models.UniqueConstraint(fields=("school", "branch", "academic_year", "name"), condition=Q(is_archived=False, branch__isnull=False), name="tt_bell_name_branch_uq")),
        migrations.AddConstraint("schoolbellschedule", models.UniqueConstraint(fields=("school", "academic_year"), condition=Q(is_archived=False, is_active=True, is_default=True, branch__isnull=True), name="tt_bell_default_global_uq")),
        migrations.AddConstraint("schoolbellschedule", models.UniqueConstraint(fields=("school", "branch", "academic_year"), condition=Q(is_archived=False, is_active=True, is_default=True, branch__isnull=False), name="tt_bell_default_branch_uq")),
        migrations.RemoveConstraint("classschedule", "timetable_schedule_section_period_uniq"),
        migrations.RemoveConstraint("classschedule", "timetable_schedule_teacher_period_uniq"),
        migrations.AddConstraint("classschedule", models.UniqueConstraint(fields=("school", "academic_year", "section", "day_of_week", "period_number"), condition=Q(is_archived=False, timetable_plan__isnull=True), name="tt_sched_legacy_section_uq")),
        migrations.AddConstraint("classschedule", models.UniqueConstraint(fields=("school", "academic_year", "teacher", "day_of_week", "period_number"), condition=Q(is_archived=False, timetable_plan__isnull=True), name="tt_sched_legacy_teacher_uq")),
        migrations.AddConstraint("classschedule", models.UniqueConstraint(fields=("timetable_plan", "section", "day_of_week", "period_number"), condition=Q(is_archived=False, timetable_plan__isnull=False), name="tt_sched_plan_section_uq")),
        migrations.AddConstraint("classschedule", models.UniqueConstraint(fields=("timetable_plan", "teacher", "day_of_week", "period_number"), condition=Q(is_archived=False, timetable_plan__isnull=False), name="tt_sched_plan_teacher_uq")),
        migrations.AddConstraint("timetableplan", models.UniqueConstraint(fields=("school", "academic_year", "version"), condition=Q(is_archived=False, branch__isnull=True), name="tt_plan_version_global_uq")),
        migrations.AddConstraint("timetableplan", models.UniqueConstraint(fields=("school", "branch", "academic_year", "version"), condition=Q(is_archived=False, branch__isnull=False), name="tt_plan_version_branch_uq")),
        migrations.AddConstraint("timetableplan", models.UniqueConstraint(fields=("school", "academic_year"), condition=Q(is_archived=False, status="published", is_current=True, branch__isnull=True), name="tt_plan_current_global_uq")),
        migrations.AddConstraint("timetableplan", models.UniqueConstraint(fields=("school", "branch", "academic_year"), condition=Q(is_archived=False, status="published", is_current=True, branch__isnull=False), name="tt_plan_current_branch_uq")),
        migrations.AddIndex("timetableplan", models.Index(fields=["school", "academic_year", "status"], name="tt_plan_school_status_idx")),
    ]
