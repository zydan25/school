# Generated for branch-scoped academic structures.
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_section_floor_wing_section_supervisor_user"),
    ]

    operations = [
        migrations.RemoveConstraint("academicyear", "academics_year_school_code_uniq"),
        migrations.RemoveConstraint("academicyear", "academics_one_current_year_per_school"),
        migrations.RemoveConstraint("academicterm", "academics_term_year_number_uniq"),
        migrations.RemoveConstraint("academicterm", "academics_one_current_term_per_year"),
        migrations.RemoveConstraint("educationalstage", "academics_stage_school_code_uniq"),
        migrations.RemoveConstraint("gradelevel", "academics_grade_school_code_uniq"),
        migrations.RemoveConstraint("classroom", "academics_classroom_school_code_uniq"),
        migrations.RemoveConstraint("section", "academics_section_school_year_code_uniq"),
        migrations.RemoveConstraint("subject", "academics_subject_school_code_uniq"),
        migrations.RemoveConstraint("perioddefinition", "academics_period_school_num_uniq"),
        migrations.RemoveConstraint("schoolworkingday", "academics_workday_school_weekday_uniq"),
        migrations.AddConstraint("academicyear", models.UniqueConstraint(fields=("school", "code"), condition=Q(branch__isnull=True), name="acad_year_code_global_uq")),
        migrations.AddConstraint("academicyear", models.UniqueConstraint(fields=("school", "branch", "code"), condition=Q(branch__isnull=False), name="acad_year_code_branch_uq")),
        migrations.AddConstraint("academicyear", models.UniqueConstraint(fields=("school",), condition=Q(is_current=True, is_archived=False, branch__isnull=True), name="acad_year_curr_global_uq")),
        migrations.AddConstraint("academicyear", models.UniqueConstraint(fields=("school", "branch"), condition=Q(is_current=True, is_archived=False, branch__isnull=False), name="acad_year_curr_branch_uq")),
        migrations.AddConstraint("academicterm", models.UniqueConstraint(fields=("academic_year", "number"), condition=Q(branch__isnull=True), name="acad_term_num_global_uq")),
        migrations.AddConstraint("academicterm", models.UniqueConstraint(fields=("academic_year", "branch", "number"), condition=Q(branch__isnull=False), name="acad_term_num_branch_uq")),
        migrations.AddConstraint("academicterm", models.UniqueConstraint(fields=("academic_year",), condition=Q(is_current=True, is_archived=False, branch__isnull=True), name="acad_term_curr_global_uq")),
        migrations.AddConstraint("academicterm", models.UniqueConstraint(fields=("academic_year", "branch"), condition=Q(is_current=True, is_archived=False, branch__isnull=False), name="acad_term_curr_branch_uq")),
        migrations.AddConstraint("educationalstage", models.UniqueConstraint(fields=("school", "code"), condition=Q(branch__isnull=True), name="acad_stage_code_global_uq")),
        migrations.AddConstraint("educationalstage", models.UniqueConstraint(fields=("school", "branch", "code"), condition=Q(branch__isnull=False), name="acad_stage_code_branch_uq")),
        migrations.AddConstraint("gradelevel", models.UniqueConstraint(fields=("school", "code"), condition=Q(branch__isnull=True), name="acad_grade_code_global_uq")),
        migrations.AddConstraint("gradelevel", models.UniqueConstraint(fields=("school", "branch", "code"), condition=Q(branch__isnull=False), name="acad_grade_code_branch_uq")),
        migrations.AddConstraint("classroom", models.UniqueConstraint(fields=("school", "code"), condition=Q(branch__isnull=True), name="acad_room_code_global_uq")),
        migrations.AddConstraint("classroom", models.UniqueConstraint(fields=("school", "branch", "code"), condition=Q(branch__isnull=False), name="acad_room_code_branch_uq")),
        migrations.AddConstraint("section", models.UniqueConstraint(fields=("school", "academic_year", "code"), condition=Q(branch__isnull=True), name="acad_section_code_global_uq")),
        migrations.AddConstraint("section", models.UniqueConstraint(fields=("school", "branch", "academic_year", "code"), condition=Q(branch__isnull=False), name="acad_section_code_branch_uq")),
        migrations.AddConstraint("subject", models.UniqueConstraint(fields=("school", "code"), condition=Q(branch__isnull=True), name="acad_subject_code_global_uq")),
        migrations.AddConstraint("subject", models.UniqueConstraint(fields=("school", "branch", "code"), condition=Q(branch__isnull=False), name="acad_subject_code_branch_uq")),
        migrations.AddConstraint("perioddefinition", models.UniqueConstraint(fields=("school", "period_number"), condition=Q(branch__isnull=True), name="acad_period_num_global_uq")),
        migrations.AddConstraint("perioddefinition", models.UniqueConstraint(fields=("school", "branch", "period_number"), condition=Q(branch__isnull=False), name="acad_period_num_branch_uq")),
        migrations.AddConstraint("schoolworkingday", models.UniqueConstraint(fields=("school", "weekday"), condition=Q(branch__isnull=True), name="acad_workday_global_uq")),
        migrations.AddConstraint("schoolworkingday", models.UniqueConstraint(fields=("school", "branch", "weekday"), condition=Q(branch__isnull=False), name="acad_workday_branch_uq")),
    ]
