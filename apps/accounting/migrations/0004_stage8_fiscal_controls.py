# Generated for stage 8 accounting controls.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0003_journalentry_is_reversed_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fiscalyear",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ إقفال السنة"),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="closed_fiscal_years",
                to=settings.AUTH_USER_MODEL,
                verbose_name="المسؤول عن الإقفال",
            ),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="closing_entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="closed_fiscal_years",
                to="accounting.journalentry",
                verbose_name="قيد إقفال السنة",
            ),
        ),
        migrations.AddField(
            model_name="fiscalyear",
            name="opening_entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="opened_fiscal_years",
                to="accounting.journalentry",
                verbose_name="قيد افتتاح السنة",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiod",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ إقفال الفترة"),
        ),
        migrations.AddField(
            model_name="fiscalperiod",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="closed_fiscal_periods",
                to=settings.AUTH_USER_MODEL,
                verbose_name="المسؤول عن إقفال الفترة",
            ),
        ),
        migrations.AddIndex(
            model_name="journalentry",
            index=models.Index(
                fields=["school", "source_module", "source_reference"],
                name="acct_journal_source_idx",
            ),
        ),
    ]
