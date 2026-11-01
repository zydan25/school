# Stage 9 HR workflows: contract and loan audit controls.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0007_stage8_treasury_defaults"),
        ("payroll", "0004_employeeloanrepayment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="employeeloanadvance",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "طلب قيد المراجعة"),
                    ("approved", "معتمدة بانتظار الصرف"),
                    ("active", "مصروفة وقيد الاستقطاع"),
                    ("fully_repaid", "مسددة بالكامل"),
                    ("written_off", "معفاة / مشطوبة"),
                ],
                default="pending",
                max_length=20,
                verbose_name="حالة السلفة",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanadvance",
            name="requested_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="requested_employee_loans", to=settings.AUTH_USER_MODEL,
                verbose_name="مقدم طلب السلفة",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanadvance",
            name="approved_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_employee_loans", to=settings.AUTH_USER_MODEL,
                verbose_name="معتمد السلفة",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanadvance",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ اعتماد السلفة"),
        ),
        migrations.AddField(
            model_name="employeeloanadvance",
            name="disbursed_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="disbursed_employee_loans", to=settings.AUTH_USER_MODEL,
                verbose_name="مسؤول صرف السلفة",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanadvance",
            name="disbursed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ صرف السلفة"),
        ),
        migrations.AddField(
            model_name="employeeloanadvance",
            name="disbursement_voucher",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="employee_loans", to="accounting.paymentvoucher",
                verbose_name="سند صرف السلفة",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeloanadvance",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="payroll_loan_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeloanadvance",
            constraint=models.CheckConstraint(
                condition=models.Q(("monthly_installment__gt", 0)),
                name="payroll_loan_installment_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeloanadvance",
            constraint=models.CheckConstraint(
                condition=models.Q(("repaid_amount__gte", 0), ("repaid_amount__lte", models.F("amount"))),
                name="payroll_loan_repaid_range",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanrepayment",
            name="idempotency_key",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="مفتاح منع تكرار السداد"),
        ),
        migrations.AddField(
            model_name="employeeloanrepayment",
            name="receipt_voucher",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="employee_loan_repayments", to="accounting.receiptvoucher",
                verbose_name="سند تحصيل السداد اليدوي",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanrepayment",
            name="recorded_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="recorded_employee_loan_repayments", to=settings.AUTH_USER_MODEL,
                verbose_name="مسجل عملية السداد",
            ),
        ),
        migrations.AddField(
            model_name="employeeloanrepayment",
            name="notes",
            field=models.CharField(blank=True, max_length=500, verbose_name="ملاحظات السداد"),
        ),
        migrations.AddConstraint(
            model_name="employeeloanrepayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key__gt", ""), ("is_archived", False)),
                fields=("school", "idempotency_key"),
                name="payroll_loan_repay_idem_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeloanrepayment",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="payroll_loan_repayment_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeloanrepayment",
            constraint=models.CheckConstraint(
                condition=models.Q(("balance_before__gte", 0), ("balance_after__gte", 0)),
                name="payroll_loan_repayment_balances_nonnegative",
            ),
        ),
    ]
