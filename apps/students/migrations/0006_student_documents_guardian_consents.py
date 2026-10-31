# Created for student documents and guardian consent tracking.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models
import apps.students.models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0005_studentmovement_unique_account_binding"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("title", models.CharField(max_length=180, verbose_name="عنوان الوثيقة")),
                ("document_type", models.CharField(choices=[("birth_certificate", "شهادة ميلاد"), ("identity", "هوية / إقامة"), ("medical", "وثيقة طبية"), ("academic", "وثيقة أكاديمية"), ("custody", "وثيقة ولاية / حضانة"), ("other", "أخرى")], default="other", max_length=30, verbose_name="نوع الوثيقة")),
                ("file", models.FileField(upload_to=apps.students.models.student_document_upload_path, validators=[apps.students.models.validate_student_document_file], verbose_name="ملف الوثيقة")),
                ("description", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("issued_on", models.DateField(blank=True, null=True, verbose_name="تاريخ الإصدار")),
                ("expires_on", models.DateField(blank=True, null=True, verbose_name="تاريخ الانتهاء")),
                ("visible_to_guardian", models.BooleanField(default=True, verbose_name="متاحة لولي الأمر المرتبط")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="documents", to="students.student", verbose_name="الطالب")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uploaded_student_documents", to=settings.AUTH_USER_MODEL, verbose_name="رفع الوثيقة")),
            ],
            options={
                "verbose_name": "وثيقة طالب",
                "verbose_name_plural": "وثائق الطلاب",
            },
        ),
        migrations.AddIndex(
            model_name="studentdocument",
            index=models.Index(fields=["school", "student", "created_at"], name="stdoc_school_stud_date_idx"),
        ),
        migrations.CreateModel(
            name="GuardianConsent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("consent_type", models.CharField(choices=[("trip", "رحلة / نشاط خارجي"), ("media", "تصوير ونشر"), ("medical", "إجراء طبي"), ("academic", "إجراء أكاديمي"), ("data", "استخدام البيانات"), ("general", "موافقة عامة")], default="general", max_length=20, verbose_name="نوع الموافقة")),
                ("title", models.CharField(max_length=180, verbose_name="عنوان الطلب")),
                ("details", models.TextField(verbose_name="تفاصيل الموافقة المطلوبة")),
                ("status", models.CharField(choices=[("pending", "بانتظار رد ولي الأمر"), ("approved", "تمت الموافقة"), ("rejected", "مرفوضة"), ("canceled", "ملغاة"), ("expired", "منتهية")], db_index=True, default="pending", max_length=12, verbose_name="حالة الموافقة")),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="وقت إرسال الطلب")),
                ("expires_at", models.DateTimeField(blank=True, null=True, verbose_name="موعد انتهاء الطلب")),
                ("responded_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت رد ولي الأمر")),
                ("response_note", models.TextField(blank=True, verbose_name="ملاحظة ولي الأمر")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guardian_consents", to="students.student", verbose_name="الطالب")),
                ("guardian", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consent_requests", to="students.guardian", verbose_name="ولي الأمر المعني")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_guardian_consents", to=settings.AUTH_USER_MODEL, verbose_name="منشئ طلب الموافقة")),
                ("responded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="responded_guardian_consents", to=settings.AUTH_USER_MODEL, verbose_name="صاحب الرد")),
            ],
            options={
                "verbose_name": "طلب موافقة ولي أمر",
                "verbose_name_plural": "موافقات أولياء الأمور",
            },
        ),
        migrations.AddIndex(
            model_name="guardianconsent",
            index=models.Index(fields=["school", "guardian", "status"], name="gcons_school_guard_stat_idx"),
        ),
        migrations.AddIndex(
            model_name="guardianconsent",
            index=models.Index(fields=["school", "student", "created_at"], name="gcons_school_stud_date_idx"),
        ),
    ]
