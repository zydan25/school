from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("attendance", "0004_branch_scoped_school_calendars")]

    operations = [
        migrations.RemoveConstraint(model_name="attendancepolicy", name="attendance_policy_one_active_per_year_school"),
        migrations.AddConstraint(
            model_name="attendancepolicy",
            constraint=models.UniqueConstraint(fields=("school", "academic_year"), condition=Q(is_archived=False, is_active=True, branch__isnull=True), name="att_policy_active_global_uq"),
        ),
        migrations.AddConstraint(
            model_name="attendancepolicy",
            constraint=models.UniqueConstraint(fields=("school", "branch", "academic_year"), condition=Q(is_archived=False, is_active=True, branch__isnull=False), name="att_policy_active_branch_uq"),
        ),
    ]
