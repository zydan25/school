from django.db import migrations


def align_student_branch_history(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    StudentEnrollment = apps.get_model("students", "StudentEnrollment")
    StudentMovement = apps.get_model("students", "StudentMovement")
    db_alias = schema_editor.connection.alias

    for student in Student.objects.using(db_alias).exclude(branch_id__isnull=True).only("pk", "branch_id").iterator():
        StudentEnrollment.objects.using(db_alias).filter(
            student_id=student.pk, branch_id__isnull=True,
        ).update(branch_id=student.branch_id)
        StudentMovement.objects.using(db_alias).filter(
            student_id=student.pk, branch_id__isnull=True,
        ).update(branch_id=student.branch_id)


class Migration(migrations.Migration):
    dependencies = [("students", "0007_expand_student_document_path")]

    operations = [migrations.RunPython(align_student_branch_history, migrations.RunPython.noop)]
