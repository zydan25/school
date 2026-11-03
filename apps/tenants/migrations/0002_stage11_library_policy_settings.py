# Generated for Stage 11 library policy settings.
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schoolsettings",
            name="feature_overrides",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="تخزن تعطيل خدمات المدرسة ضمن المفتاح school_services؛ لا تسمح بتجاوز ميزات الباقة.",
                verbose_name="تجاوزات المزايا",
            ),
        ),

        migrations.AddField(
            model_name="schoolsettings",
            name="library_default_loan_days",
            field=models.PositiveSmallIntegerField(default=14, verbose_name="مدة إعارة الكتاب الافتراضية بالأيام"),
        ),
        migrations.AddField(
            model_name="schoolsettings",
            name="library_max_renewals",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="الحد الأقصى لتجديد الإعارة"),
        ),
        migrations.AddField(
            model_name="schoolsettings",
            name="library_overdue_fine_per_day",
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name="غرامة تأخير الكتاب عن كل يوم"),
        ),
        migrations.AddField(
            model_name="schoolsettings",
            name="library_max_overdue_fine",
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name="الحد الأعلى لغرامة التأخير (صفر بلا حد)"),
        ),
        migrations.AddField(
            model_name="schoolsettings",
            name="library_lost_book_fine",
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name="غرامة الكتاب المفقود"),
        ),
    ]
