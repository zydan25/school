# Generated for Stage 11 optional school services.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def seed_school_service_features(apps, schema_editor):
    Feature = apps.get_model("platform", "Feature")
    definitions = (
        (
            "school-transport",
            "النقل المدرسي",
            "النقل والحافلات وخطوط السير واشتراكات الطلاب والتسويات المالية.",
        ),
        (
            "school-library",
            "المكتبة المدرسية",
            "إدارة الكتب والإعارة والإرجاع والتجديد والغرامات.",
        ),
        (
            "school-book-distribution",
            "توزيع الكتب وأوامر الصرف",
            "توزيع الكتب على الطلاب وأوامر الصرف المرتبطة بالمخزون والرسوم.",
        ),
    )
    for code, name, description in definitions:
        Feature.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "module_key": "school_services",
                "is_active": True,
                "is_addon": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("school_services", "0006_studentbookdistribution_returned_at_and_more"),
        ("platform", "0001_initial"),
        ("student_fees", "0007_stage7_student_fee_workflows"),
        ("tenants", "0002_stage11_library_policy_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="bookloan",
            name="fine_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="library_fine_loans",
                to="student_fees.studentinvoice",
                verbose_name="فاتورة غرامة الإعارة",
            ),
        ),
        migrations.AddField(
            model_name="bookloan",
            name="renewal_count",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="عدد مرات التجديد"),
        ),
        migrations.AlterField(
            model_name="bookloan",
            name="fine_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="غرامة التأخير أو التلف (إن وجدت)"),
        ),

        migrations.CreateModel(
            name="BusSubscriptionCharge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("billing_year", models.PositiveSmallIntegerField(verbose_name="سنة الفوترة")),
                ("billing_month", models.PositiveSmallIntegerField(verbose_name="شهر الفوترة")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="قيمة الفاتورة وقت الإصدار")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_bus_subscription_charges", to=settings.AUTH_USER_MODEL, verbose_name="أصدرها")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="bus_subscription_charge", to="student_fees.studentinvoice", verbose_name="فاتورة الطالب")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="monthly_charges", to="school_services.studentbussubscription", verbose_name="اشتراك النقل")),
            ],
            options={
                "verbose_name": "فاتورة اشتراك نقل",
                "verbose_name_plural": "فواتير اشتراكات النقل",
                "constraints": [
                    models.UniqueConstraint(
                        condition=Q(is_archived=False),
                        fields=("school", "subscription", "billing_year", "billing_month"),
                        name="school_services_bus_charge_period_uniq",
                    ),
                    models.CheckConstraint(
                        condition=Q(billing_month__gte=1) & Q(billing_month__lte=12),
                        name="school_services_bus_charge_month_valid",
                    ),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="busroute",
            options={
                "verbose_name": "خط سير حافلة",
                "verbose_name_plural": "خطوط النقل المدرسي",
                "permissions": [
                    ("bill_studentbussubscription", "يمكنه إصدار فواتير اشتراكات النقل"),
                ],
            },
        ),
        migrations.AlterField(
            model_name="bookrequisitionorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "مسودة طلب"),
                    ("submitted", "مرفوع للاعتماد الإداري"),
                    ("approved", "معتمد - موجه لأمين المستودع"),
                    ("fulfilled", "تم الصرف والتسليم من المخزن"),
                    ("rejected", "مرفوض"),
                ],
                default="draft",
                max_length=20,
                verbose_name="حالة أمر الصرف",
            ),
        ),
        migrations.AlterModelOptions(
            name="librarybook",
            options={
                "verbose_name": "كتاب مدرسي / مرجع",
                "verbose_name_plural": "المكتبة المدرسية والكتب",
                "permissions": [
                    ("manage_library_policy", "يمكنه إدارة سياسة المكتبة والغرامات"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="bookloan",
            options={
                "verbose_name": "سجل إعارة كتاب",
                "verbose_name_plural": "إعارات المكتبة المدرسية",
                "permissions": [
                    ("return_bookloan", "يمكنه إرجاع كتاب مستعار"),
                    ("renew_bookloan", "يمكنه تجديد إعارة كتاب"),
                    ("marklost_bookloan", "يمكنه تسجيل كتاب مستعار كمفقود"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="busfinancialsettlement",
            options={
                "verbose_name": "تسوية مالية لحافلة",
                "verbose_name_plural": "المحاسبة المالية للحافلات والسائقين",
                "permissions": [
                    ("calculate_busfinancialsettlement", "يمكنه احتساب تسوية النقل"),
                    ("approve_busfinancialsettlement", "يمكنه اعتماد تسوية النقل وصرفها"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="studentbookdistribution",
            options={
                "verbose_name": "تسليم كتب مدرسية",
                "verbose_name_plural": "توزيع الكتب المدرسية ورسومها",
                "permissions": [
                    ("deliver_studentbookdistribution", "يمكنه تسليم الكتب للطلاب"),
                    ("return_studentbookdistribution", "يمكنه استرجاع الكتب من الطلاب"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="bookrequisitionorder",
            options={
                "verbose_name": "أمر صرف كتب ومستلزمات",
                "verbose_name_plural": "أوامر صرف الكتب من المستودع",
                "permissions": [
                    ("submit_bookrequisitionorder", "يمكنه رفع أمر صرف كتب"),
                    ("approve_bookrequisitionorder", "يمكنه اعتماد أمر صرف كتب"),
                    ("reject_bookrequisitionorder", "يمكنه رفض أمر صرف كتب"),
                    ("fulfill_bookrequisitionorder", "يمكنه تنفيذ صرف أمر الكتب"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BookRequisitionFulfillment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("idempotency_key", models.CharField(max_length=80, verbose_name="مفتاح منع تكرار طلب الصرف")),
                ("payload_hash", models.CharField(max_length=64, verbose_name="بصمة بيانات الصرف")),
                ("line_count", models.PositiveSmallIntegerField(verbose_name="عدد البنود المصروفة")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="book_requisition_fulfillments", to=settings.AUTH_USER_MODEL, verbose_name="نفذ الصرف")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("requisition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fulfillment_batches", to="school_services.bookrequisitionorder", verbose_name="أمر الصرف")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={
                "verbose_name": "دفعة تنفيذ أمر صرف كتب",
                "verbose_name_plural": "دفعات تنفيذ أوامر صرف الكتب",
                "ordering": ("-created_at",),
                "constraints": [
                    models.UniqueConstraint(
                        condition=Q(is_archived=False),
                        fields=("school", "idempotency_key"),
                        name="school_services_requisition_fulfil_key_uniq",
                    ),
                ],
            },
        ),
        migrations.RunPython(seed_school_service_features, migrations.RunPython.noop),
    ]
