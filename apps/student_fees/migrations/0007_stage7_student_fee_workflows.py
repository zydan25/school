import uuid
from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def backfill_fee_record_branches(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    StudentInvoice = apps.get_model("student_fees", "StudentInvoice")
    StudentInvoiceItem = apps.get_model("student_fees", "StudentInvoiceItem")
    PaymentReceipt = apps.get_model("student_fees", "PaymentReceipt")
    StudentCreditTransaction = apps.get_model("student_fees", "StudentCreditTransaction")
    PaymentAllocation = apps.get_model("student_fees", "PaymentAllocation")
    FeeInstallmentPlan = apps.get_model("student_fees", "FeeInstallmentPlan")
    FeeInstallment = apps.get_model("student_fees", "FeeInstallment")
    JournalEntry = apps.get_model("accounting", "JournalEntry")
    JournalEntryLine = apps.get_model("accounting", "JournalEntryLine")

    def assign_journal_branch(journal_id, branch_id):
        JournalEntry.objects.using(db_alias).filter(
            pk=journal_id, branch__isnull=True,
        ).update(branch_id=branch_id)
        JournalEntryLine.objects.using(db_alias).filter(
            journal_entry_id=journal_id, branch__isnull=True,
        ).update(branch_id=branch_id)

    for invoice in StudentInvoice.objects.using(db_alias).filter(branch__isnull=True).select_related("student"):
        if invoice.student.branch_id:
            StudentInvoice.objects.using(db_alias).filter(pk=invoice.pk).update(branch_id=invoice.student.branch_id)

    for item in StudentInvoiceItem.objects.using(db_alias).filter(
        branch__isnull=True, invoice__branch__isnull=False,
    ).select_related("invoice"):
        StudentInvoiceItem.objects.using(db_alias).filter(pk=item.pk).update(branch_id=item.invoice.branch_id)

    for receipt in PaymentReceipt.objects.using(db_alias).filter(
        branch__isnull=True, student__branch__isnull=False,
    ).select_related("student"):
        PaymentReceipt.objects.using(db_alias).filter(pk=receipt.pk).update(branch_id=receipt.student.branch_id)

    for credit_tx in StudentCreditTransaction.objects.using(db_alias).filter(
        branch__isnull=True, student__branch__isnull=False,
    ).select_related("student"):
        StudentCreditTransaction.objects.using(db_alias).filter(pk=credit_tx.pk).update(branch_id=credit_tx.student.branch_id)

    for allocation in PaymentAllocation.objects.using(db_alias).filter(
        branch__isnull=True, invoice__branch__isnull=False,
    ).select_related("invoice"):
        PaymentAllocation.objects.using(db_alias).filter(pk=allocation.pk).update(branch_id=allocation.invoice.branch_id)

    for plan in FeeInstallmentPlan.objects.using(db_alias).filter(
        branch__isnull=True, invoice__branch__isnull=False,
    ).select_related("invoice"):
        FeeInstallmentPlan.objects.using(db_alias).filter(pk=plan.pk).update(branch_id=plan.invoice.branch_id)

    for installment in FeeInstallment.objects.using(db_alias).filter(
        branch__isnull=True, plan__branch__isnull=False,
    ).select_related("plan"):
        FeeInstallment.objects.using(db_alias).filter(pk=installment.pk).update(branch_id=installment.plan.branch_id)

    # Carry branch attribution to the financial journal entries linked to
    # invoices, receipts and credit-settlement source transactions.
    for invoice in StudentInvoice.objects.using(db_alias).filter(
        branch__isnull=False, journal_entry__isnull=False,
        journal_entry__branch__isnull=True,
    ).select_related("journal_entry"):
        assign_journal_branch(invoice.journal_entry_id, invoice.branch_id)

    for receipt in PaymentReceipt.objects.using(db_alias).filter(
        branch__isnull=False, journal_entry__isnull=False,
        journal_entry__branch__isnull=True,
    ).select_related("journal_entry"):
        assign_journal_branch(receipt.journal_entry_id, receipt.branch_id)

    for credit_tx in StudentCreditTransaction.objects.using(db_alias).filter(
        transaction_type="usage", invoice__isnull=False,
        invoice__branch__isnull=False,
    ).iterator(chunk_size=500):
        for journal_id in JournalEntry.objects.using(db_alias).filter(
            school_id=credit_tx.school_id,
            source_module="student_fees_credit",
            source_reference=str(credit_tx.pk),
            branch__isnull=True,
        ).values_list("pk", flat=True):
            assign_journal_branch(journal_id, credit_tx.branch_id)

    for reversal in JournalEntry.objects.using(db_alias).filter(
        source_module="reversal", branch__isnull=True,
    ).iterator(chunk_size=500):
        original = JournalEntry.objects.using(db_alias).filter(
            school_id=reversal.school_id,
            entry_number=reversal.source_reference,
            branch__isnull=False,
        ).first()
        if original:
            assign_journal_branch(reversal.pk, original.branch_id)

    # Preserve pre-existing positive balances and align every opening balance
    # with the append-only credit ledger without changing a student's balance.
    Student = apps.get_model("students", "Student")
    candidates = Student.objects.using(db_alias).filter(
        Q(credit_balance__gt=Decimal("0.00"))
        | Q(credit_transactions__isnull=False)
    ).distinct().iterator(chunk_size=500)
    for student in candidates:
        latest = StudentCreditTransaction.objects.using(db_alias).filter(
            student_id=student.pk,
        ).order_by("-created_at", "-pk").first()
        ledger_balance = latest.balance_after if latest else Decimal("0.00")
        if (
            ledger_balance >= Decimal("0.00")
            and student.credit_balance >= Decimal("0.00")
            and ledger_balance != student.credit_balance
        ):
            StudentCreditTransaction.objects.using(db_alias).create(
                school_id=student.school_id,
                branch_id=student.branch_id,
                student_id=student.pk,
                transaction_type="adjustment",
                amount=abs(student.credit_balance - ledger_balance),
                balance_before=ledger_balance,
                balance_after=student.credit_balance,
                created_by_id=None,
                notes=(
                    "تسوية افتتاحية آلية لمطابقة الرصيد الدائن القائم مع دفتر الحركات "
                    "عند ترقية نظام رسوم الطلاب إلى المرحلة السابعة."
                ),
            )


class Migration(migrations.Migration):

    dependencies = [
        ("student_fees", "0006_studentcredittransaction_is_reversed_and_more"),
        ("students", "0008_align_student_branch_history"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="studentinvoice",
            name="notes",
            field=models.TextField(blank=True, verbose_name="ملاحظات الفاتورة"),
        ),
        migrations.AddField(
            model_name="studentinvoice",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=128, verbose_name="مفتاح منع تكرار إنشاء الفاتورة"),
        ),
        migrations.AddField(
            model_name="paymentreceipt",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=128, verbose_name="مفتاح منع تكرار العملية"),
        ),
        migrations.AddField(
            model_name="studentcredittransaction",
            name="refund_payment_method",
            field=models.CharField(
                blank=True, choices=[
                    ("cash", "نقداً (صندوق المدرسة)"),
                    ("bank_transfer", "تحويل بنكي"),
                    ("pos", "شبكة / نقطة بيع"),
                    ("online", "دفع إلكتروني مباشر"),
                ], max_length=20, verbose_name="طريقة صرف الاسترداد",
            ),
        ),
        migrations.AddField(
            model_name="studentcredittransaction",
            name="refund_reference",
            field=models.CharField(blank=True, max_length=100, verbose_name="مرجع عملية الاسترداد"),
        ),
        migrations.AddField(
            model_name="studentcredittransaction",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=128, verbose_name="مفتاح منع تكرار الاسترداد"),
        ),
        migrations.AlterField(
            model_name="paymentallocation",
            name="receipt",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="allocations", to="student_fees.paymentreceipt",
                verbose_name="سند القبض",
            ),
        ),
        migrations.AddField(
            model_name="paymentallocation",
            name="credit_transaction",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="allocations", to="student_fees.studentcredittransaction",
                verbose_name="حركة استخدام الرصيد الدائن",
            ),
        ),
        migrations.RunPython(backfill_fee_record_branches, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="feestructure",
            name="student_fees_structure_uniq",
        ),
        migrations.AddConstraint(
            model_name="feestructure",
            constraint=models.UniqueConstraint(
                fields=("school", "academic_year", "grade_level", "fee_category"),
                condition=Q(is_archived=False, branch__isnull=True),
                name="student_fees_structure_global_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="feestructure",
            constraint=models.UniqueConstraint(
                fields=("school", "branch", "academic_year", "grade_level", "fee_category"),
                condition=Q(is_archived=False, branch__isnull=False),
                name="student_fees_structure_branch_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="studentinvoice",
            constraint=models.UniqueConstraint(
                fields=("school", "idempotency_key"),
                condition=~Q(idempotency_key=""),
                name="student_fees_invoice_idempotency_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentreceipt",
            constraint=models.UniqueConstraint(
                fields=("school", "idempotency_key"),
                condition=~Q(idempotency_key=""),
                name="student_fees_receipt_idempotency_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="studentcredittransaction",
            constraint=models.UniqueConstraint(
                fields=("school", "idempotency_key"),
                condition=~Q(idempotency_key=""),
                name="student_credit_idempotency_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentallocation",
            constraint=models.CheckConstraint(
                condition=(
                    Q(receipt__isnull=False, credit_transaction__isnull=True)
                    | Q(receipt__isnull=True, credit_transaction__isnull=False)
                ),
                name="student_fees_allocation_one_source",
            ),
        ),
        migrations.CreateModel(
            name="FeeDiscountPolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("max_discount_percent", models.DecimalField(decimal_places=2, default=Decimal("100.00"), max_digits=5, verbose_name="الحد الأعلى لنسبة الخصم")),
                ("auto_approval_limit", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, verbose_name="حد الاعتماد التلقائي")),
                ("allow_full_exemption", models.BooleanField(default=False, verbose_name="السماح بالإعفاء الكامل")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={
                "verbose_name": "سياسة خصومات الرسوم",
                "verbose_name_plural": "سياسات خصومات الرسوم",
            },
        ),
        migrations.AddConstraint(
            model_name="feediscountpolicy",
            constraint=models.UniqueConstraint(
                fields=("school",), condition=Q(is_archived=False),
                name="student_fee_discount_policy_school_uniq",
            ),
        ),
        migrations.CreateModel(
            name="FeeDiscountRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(db_index=True, default=False, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الأرشفة")),
                ("idempotency_key", models.CharField(blank=True, max_length=128, verbose_name="مفتاح منع تكرار طلب الخصم")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="قيمة الخصم المطلوب")),
                ("reason", models.TextField(verbose_name="مبرر الخصم أو الإعفاء")),
                ("status", models.CharField(choices=[("pending", "بانتظار الاعتماد"), ("approved", "معتمد"), ("rejected", "مرفوض")], default="pending", max_length=12, verbose_name="حالة الطلب")),
                ("decided_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت القرار")),
                ("decision_notes", models.TextField(blank=True, verbose_name="ملاحظات القرار")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_student_fee_discounts", to=settings.AUTH_USER_MODEL, verbose_name="صاحب قرار الاعتماد")),
                ("archived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_archived", to=settings.AUTH_USER_MODEL, verbose_name="أرشفه")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.branch", verbose_name="الفرع")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="discount_requests", to="student_fees.studentinvoice", verbose_name="الفاتورة")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_fee_discount_requests", to=settings.AUTH_USER_MODEL, verbose_name="مقدم الطلب")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="tenants.school", verbose_name="المدرسة")),
            ],
            options={
                "verbose_name": "طلب خصم رسوم",
                "verbose_name_plural": "طلبات خصومات وإعفاءات الرسوم",
            },
        ),
        migrations.AddConstraint(
            model_name="feediscountrequest",
            constraint=models.UniqueConstraint(
                fields=("school", "invoice"),
                condition=Q(status="pending", is_archived=False),
                name="student_fee_one_pending_discount_invoice",
            ),
        ),
        migrations.AddConstraint(
            model_name="feediscountrequest",
            constraint=models.UniqueConstraint(
                fields=("school", "idempotency_key"),
                condition=~Q(idempotency_key=""),
                name="student_fee_discount_idempotency_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="feediscountrequest",
            index=models.Index(
                fields=["school", "status", "created_at"],
                name="st_fee_disc_school_idx",
            ),
        ),
    ]
