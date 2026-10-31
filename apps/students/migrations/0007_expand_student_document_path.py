# Expand the private document path to hold school, student and UUID segments.
import apps.students.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0006_student_documents_guardian_consents"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studentdocument",
            name="file",
            field=models.FileField(
                max_length=255,
                upload_to=apps.students.models.student_document_upload_path,
                validators=[apps.students.models.validate_student_document_file],
                verbose_name="ملف الوثيقة",
            ),
        ),
    ]
