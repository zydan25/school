from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0004_branch_scoped_academic_structure"),
        ("attendance", "0003_attendancepolicy_cascade_daily_to_periods_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="schoolcalendar",
            name="attendance_calendar_school_year_name_uniq",
        ),
        migrations.AddConstraint(
            model_name="schoolcalendar",
            constraint=models.UniqueConstraint(
                fields=("school", "academic_year", "name"),
                condition=Q(is_archived=False, branch__isnull=True),
                name="att_cal_name_global_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="schoolcalendar",
            constraint=models.UniqueConstraint(
                fields=("school", "branch", "academic_year", "name"),
                condition=Q(is_archived=False, branch__isnull=False),
                name="att_cal_name_branch_uq",
            ),
        ),
    ]
