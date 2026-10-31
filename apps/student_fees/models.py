"""Student fees, invoicing, installment plans, and payment receipt domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class FeeCategory(TenantOwnedModel):
    """بنود وتصنيفات الرسوم المدرسية (رسوم دراسية، نقل، كتب، زي)."""
    name = models.CharField("اسم بند الرسوم", max_length=150)
    code = models.CharField("رمز البند", max_length=50)
    description = models.TextField("وصف البند", blank=True)
    is_mandatory = models.BooleanField("بند إلزامي لكافة الطلاب", default=True)

    class Meta:
        verbose_name = "بند رسوم"
        verbose_name_plural = "بنود وتصنيفات الرسوم"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="student_fees_cat_school_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class FeeStructure(TenantOwnedModel):
    """هيكل الرسوم السنوي المعتمد لكل صف دراسي."""
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="fee_structures",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي",
        on_delete=models.PROTECT,
        related_name="fee_structures",
    )
    fee_category = models.ForeignKey(
        FeeCategory,
        verbose_name="بند الرسوم",
        on_delete=models.PROTECT,
        related_name="structures",
    )
    amount = models.DecimalField("قيمة الرسم المالي", max_digits=12, decimal_places=2)
    due_date = models.DateField("موعد استحقاق السداد الافتراضي", null=True, blank=True)

    class Meta:
        verbose_name = "هيكل رسوم صف"
        verbose_name_plural = "هياكل الرسوم الدراسية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "grade_level", "fee_category"],
                condition=models.Q(is_archived=False),
                name="student_fees_structure_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.grade_level.name} - {self.fee_category.name}: {self.amount}"


class StudentInvoice(TenantOwnedModel):
    """فاتورة المطالبة المالية للطالب."""
    class Status(models.TextChoices):
        UNPAID = "unpaid", "غير مسددة"
        PARTIAL = "partially_paid", "مسددة جزئياً"
        PAID = "paid", "مسددة بالكامل"
        CANCELLED = "cancelled", "ملغاة"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المطالب",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="student_invoices",
    )
    invoice_number = models.CharField("رقم الفاتورة", max_length=50, db_index=True)
    total_amount = models.DecimalField("إجمالي قيمة الفاتورة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField("إجمالي الخصومات والمنح", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField("المبلغ المسدد حتى الآن", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة الفاتورة", max_length=20, choices=Status.choices, default=Status.UNPAID)
    issue_date = models.DateField("تاريخ إصدار الفاتورة", default=timezone.localdate)
    due_date = models.DateField("تاريخ الاستحقاق")
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        verbose_name="قيد الاستحقاق المحاسبي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_invoices",
    )

    class Meta:
        verbose_name = "فاتورة طالب"
        verbose_name_plural = "فواتير الطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "invoice_number"],
                condition=models.Q(is_archived=False),
                name="student_fees_invoice_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "student", "status"]),
            models.Index(fields=["school", "due_date"]),
        ]

    def __str__(self) -> str:
        return f"فاتورة #{self.invoice_number} - {self.student}: {self.total_amount} ({self.get_status_display()})"

    @property
    def remaining_amount(self) -> Decimal:
        net_payable = max(Decimal("0.00"), self.total_amount - self.discount_amount)
        return max(Decimal("0.00"), net_payable - self.paid_amount)

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})

    def post_to_journal(self):
        """ترحيل الفاتورة إلى قيد استحقاق محاسبي مزدوج (Accrual Posting)."""
        from apps.accounting.services.auto_posting import post_student_invoice_to_journal
        entry = post_student_invoice_to_journal(self)
        if entry and not self.journal_entry_id:
            self.journal_entry = entry
            self.save(update_fields=["journal_entry", "updated_at"])
        return entry


class StudentInvoiceItem(TenantOwnedModel):
    """البنود التفصيلية داخل فاتورة الطالب."""
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة التابعة لها",
        on_delete=models.CASCADE,
        related_name="items",
    )
    fee_category = models.ForeignKey(
        FeeCategory,
        verbose_name="بند الرسم",
        on_delete=models.PROTECT,
        related_name="invoice_items",
    )
    description = models.CharField("بيان البند", max_length=255)
    amount = models.DecimalField("القيمة الإجمالية", max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField("قيمة الخصم إن وجد", max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "بند فاتورة"
        verbose_name_plural = "بنود فواتير الطلاب"

    def __str__(self) -> str:
        return f"{self.description}: {self.amount}"


class PaymentReceipt(TenantOwnedModel):
    """سند القبض والتحصيل المالي من الطالب / ولي الأمر."""
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقداً (صندوق المدرسة)"
        BANK_TRANSFER = "bank_transfer", "تحويل بنكي"
        POS = "pos", "شبكة / نقطة بيع"
        ONLINE = "online", "دفع إلكتروني مباشر"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المسدد",
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة المرتبطة بالسداد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receipts",
    )
    receipt_number = models.CharField("رقم سند القبض", max_length=50, db_index=True)
    amount = models.DecimalField("المبلغ المحصل", max_digits=12, decimal_places=2)
    payment_method = models.CharField("طريقة الدفع", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference_number = models.CharField("رقم الإيداع / مرجع العملية البنكية", max_length=100, blank=True)
    paid_at = models.DateTimeField("تاريخ ووقت السداد", default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="أمين الصندوق / المحصل",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collected_receipts",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        verbose_name="قيد التحصيل المحاسبي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_receipts",
    )
    notes = models.TextField("ملاحظات إضافية على السند", blank=True)
    is_cancelled = models.BooleanField("ملغى / مسترد", default=False)

    class Meta:
        verbose_name = "سند قبض"
        verbose_name_plural = "سندات القبض والتحصيل"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "receipt_number"],
                condition=models.Q(is_archived=False),
                name="student_fees_receipt_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["school", "paid_at"]),
            models.Index(fields=["school", "student"]),
        ]

    def __str__(self) -> str:
        return f"سند #{self.receipt_number} - {self.student}: {self.amount} ({self.get_payment_method_display()})"

    def clean(self):
        super().clean()
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "مبلغ سند القبض يجب أن يكون أكبر من الصفر."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا ينتمي إلى نفس المدرسة."})
        if self.invoice_id:
            if self.invoice.school_id != self.school_id:
                raise ValidationError({"invoice": "الفاتورة المحددة لا تتبع نفس المدرسة."})
            if self.invoice.student_id != self.student_id:
                raise ValidationError({"invoice": "الفاتورة المحددة لا تخص هذا الطالب."})
            if self.invoice.status == StudentInvoice.Status.CANCELLED:
                raise ValidationError({"invoice": "لا يمكن سداد أو ربط سند بفاتورة ملغاة."})

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        from django.db import transaction
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new and not self.is_cancelled:
                if self.invoice:
                    inv = StudentInvoice.objects.select_for_update().get(pk=self.invoice_id)
                    net = max(Decimal("0.00"), inv.total_amount - inv.discount_amount)
                    needed = max(Decimal("0.00"), net - inv.paid_amount)
                    pay_part = min(self.amount, needed) if needed > Decimal("0.00") else Decimal("0.00")
                    if pay_part > Decimal("0.00"):
                        inv.paid_amount += pay_part
                        if inv.paid_amount >= net:
                            inv.status = StudentInvoice.Status.PAID
                        else:
                            inv.status = StudentInvoice.Status.PARTIAL
                        inv.save(update_fields=["paid_amount", "status", "updated_at"])

                        # Allocate sequentially to installments if plan exists
                        plan = inv.installment_plans.filter(is_archived=False).first()
                        allocated_any_inst = False
                        if plan:
                            rem_for_inst = pay_part
                            open_insts = plan.installments.filter(
                                status__in=[FeeInstallment.Status.PENDING, FeeInstallment.Status.PARTIAL, FeeInstallment.Status.OVERDUE],
                                is_archived=False,
                            ).order_by("due_date", "installment_number").select_for_update()

                            for inst_obj in open_insts:
                                if rem_for_inst <= Decimal("0.00"):
                                    break
                                needed_inst = inst_obj.remaining_amount
                                if needed_inst <= Decimal("0.00"):
                                    continue
                                pay_inst = min(rem_for_inst, needed_inst)
                                inst_obj.paid_amount += pay_inst
                                rem_for_inst -= pay_inst
                                if inst_obj.paid_amount >= inst_obj.amount:
                                    inst_obj.status = FeeInstallment.Status.PAID
                                else:
                                    inst_obj.status = FeeInstallment.Status.PARTIAL
                                inst_obj.paid_date = self.paid_at.date()
                                inst_obj.receipt = self
                                inst_obj.save(update_fields=["paid_amount", "status", "paid_date", "receipt", "updated_at"])

                                PaymentAllocation.objects.create(
                                    school=self.school,
                                    receipt=self,
                                    invoice=inv,
                                    installment=inst_obj,
                                    allocated_amount=pay_inst,
                                    allocated_by=self.received_by,
                                    notes="تخصيص قسط محدد بالسند",
                                )
                                allocated_any_inst = True

                        if not allocated_any_inst:
                            PaymentAllocation.objects.create(
                                school=self.school,
                                receipt=self,
                                invoice=inv,
                                installment=None,
                                allocated_amount=pay_part,
                                allocated_by=self.received_by,
                                notes="تخصيص مباشر للفاتورة المحددة بالسند",
                            )

                    excess = self.amount - pay_part
                    if excess > Decimal("0.00"):
                        student = self.student
                        bal_before = student.credit_balance
                        bal_after = bal_before + excess
                        student.credit_balance = bal_after
                        student.save(update_fields=["credit_balance"])

                        StudentCreditTransaction.objects.create(
                            school=self.school,
                            student=student,
                            transaction_type=StudentCreditTransaction.TransactionType.DEPOSIT,
                            amount=excess,
                            balance_before=bal_before,
                            balance_after=bal_after,
                            receipt=self,
                            invoice=inv,
                            created_by=self.received_by,
                            notes=f"إيداع فائض سداد سند قبض #{self.receipt_number}",
                        )
                else:
                    # Allocate chronologically across open unpaid invoices
                    remaining = self.amount
                    open_invoices = StudentInvoice.objects.filter(
                        school=self.school,
                        student=self.student,
                        status__in=[StudentInvoice.Status.UNPAID, StudentInvoice.Status.PARTIAL],
                        is_archived=False,
                    ).order_by("due_date", "created_at").select_for_update()

                    for inv in open_invoices:
                        if remaining <= Decimal("0.00"):
                            break
                        net = max(Decimal("0.00"), inv.total_amount - inv.discount_amount)
                        needed = max(Decimal("0.00"), net - inv.paid_amount)
                        if needed <= Decimal("0.00"):
                            continue
                        pay_part = min(remaining, needed)
                        inv.paid_amount += pay_part
                        remaining -= pay_part
                        if inv.paid_amount >= net:
                            inv.status = StudentInvoice.Status.PAID
                        else:
                            inv.status = StudentInvoice.Status.PARTIAL
                        inv.save(update_fields=["paid_amount", "status", "updated_at"])

                        plan = inv.installment_plans.filter(is_archived=False).first()
                        allocated_any_inst = False
                        if plan:
                            rem_for_inst = pay_part
                            open_insts = plan.installments.filter(
                                status__in=[FeeInstallment.Status.PENDING, FeeInstallment.Status.PARTIAL, FeeInstallment.Status.OVERDUE],
                                is_archived=False,
                            ).order_by("due_date", "installment_number").select_for_update()

                            for inst_obj in open_insts:
                                if rem_for_inst <= Decimal("0.00"):
                                    break
                                needed_inst = inst_obj.remaining_amount
                                if needed_inst <= Decimal("0.00"):
                                    continue
                                pay_inst = min(rem_for_inst, needed_inst)
                                inst_obj.paid_amount += pay_inst
                                rem_for_inst -= pay_inst
                                if inst_obj.paid_amount >= inst_obj.amount:
                                    inst_obj.status = FeeInstallment.Status.PAID
                                else:
                                    inst_obj.status = FeeInstallment.Status.PARTIAL
                                inst_obj.paid_date = self.paid_at.date()
                                inst_obj.receipt = self
                                inst_obj.save(update_fields=["paid_amount", "status", "paid_date", "receipt", "updated_at"])

                                PaymentAllocation.objects.create(
                                    school=self.school,
                                    receipt=self,
                                    invoice=inv,
                                    installment=inst_obj,
                                    allocated_amount=pay_inst,
                                    allocated_by=self.received_by,
                                    notes="تخصيص آلي للأقساط المجدولة",
                                )
                                allocated_any_inst = True

                        if not allocated_any_inst:
                            PaymentAllocation.objects.create(
                                school=self.school,
                                receipt=self,
                                invoice=inv,
                                installment=None,
                                allocated_amount=pay_part,
                                allocated_by=self.received_by,
                                notes="تخصيص آلي حسب تاريخ الاستحقاق",
                            )

                    # If student paid more than all open invoices, credit the excess to their credit_balance
                    if remaining > Decimal("0.00"):
                        student = self.student
                        bal_before = student.credit_balance
                        bal_after = bal_before + remaining
                        student.credit_balance = bal_after
                        student.save(update_fields=["credit_balance"])

                        StudentCreditTransaction.objects.create(
                            school=self.school,
                            student=student,
                            transaction_type=StudentCreditTransaction.TransactionType.DEPOSIT,
                            amount=remaining,
                            balance_before=bal_before,
                            balance_after=bal_after,
                            receipt=self,
                            created_by=self.received_by,
                            notes=f"إيداع فائض سداد سند قبض #{self.receipt_number}",
                        )

                # Automatic posting to journal: fail transaction if chart of accounts exists but fails
                from apps.accounting.services.auto_posting import post_student_receipt_to_journal
                entry = post_student_receipt_to_journal(self)
                if entry and not self.journal_entry_id:
                    self.journal_entry = entry
                    super().save(update_fields=["journal_entry", "updated_at"])


class StudentCreditTransaction(TenantOwnedModel):
    """دفتر حركة الأرصدة الدائنة للطلاب (سجل عمليات الفائض، السداد، والاسترداد)."""
    class TransactionType(models.TextChoices):
        DEPOSIT = "deposit", "إيداع رصيد دائن (فائض سداد سند)"
        USAGE = "usage", "استخدام رصيد دائن لسداد فاتورة"
        REFUND = "refund", "استرداد نقدي لولي الأمر"
        ADJUSTMENT = "adjustment", "تسوية إدارية / قيد تسوية"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="credit_transactions",
    )
    transaction_type = models.CharField("نوع الحركة", max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField("مبلغ الحركة", max_digits=12, decimal_places=2)
    balance_before = models.DecimalField("الرصيد قبل الحركة", max_digits=12, decimal_places=2)
    balance_after = models.DecimalField("الرصيد بعد الحركة", max_digits=12, decimal_places=2)
    receipt = models.ForeignKey(
        PaymentReceipt,
        verbose_name="سند القبض المرتبط (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_transactions",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة المرتبطة (إن وجدت)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_transactions",
    )
    source_receipt = models.ForeignKey(
        PaymentReceipt,
        verbose_name="سند القبض مصدر الفائض",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="derived_credit_usages",
    )
    is_reversed = models.BooleanField("تم عكس الحركة", default=False)
    reversed_by_transaction = models.ForeignKey(
        "self",
        verbose_name="حركة العكس المرتبطة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reverses_transactions",
    )
    created_at = models.DateTimeField("تاريخ الحركة", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المستخدم المنفذ",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_credit_transactions",
    )
    notes = models.TextField("ملاحظات وشرح الحركة", blank=True)

    class Meta:
        verbose_name = "حركة رصيد دائن لطالب"
        verbose_name_plural = "دفتر الأرصدة الدائنة للطلاب"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student} - {self.get_transaction_type_display()}: {self.amount} (الرصيد: {self.balance_after})"


def apply_credit_balance_to_invoice(student, invoice: StudentInvoice, amount: Decimal | None = None, user=None) -> StudentCreditTransaction:
    """استخدام الرصيد الدائن للطالب لسداد فاتورة مستحقة وتوثيق العملية في دفتر الأرصدة الدائنة وإثبات قيد التسوية."""
    from django.db import transaction
    if invoice.school_id != student.school_id:
        raise ValidationError("الفاتورة والطالب لا يتبعان لنفس المدرسة.")
    if invoice.student_id != student.pk:
        raise ValidationError("الفاتورة المحددة لا تخص هذا الطالب.")

    with transaction.atomic():
        locked_student = type(student).objects.select_for_update().get(pk=student.pk)
        locked_invoice = StudentInvoice.objects.select_for_update().get(pk=invoice.pk)

        if amount is None:
            amount = min(locked_student.credit_balance, locked_invoice.remaining_amount)
        if amount <= Decimal("0.00"):
            raise ValidationError("المبلغ المطلوب استخدامه من الرصيد الدائن يجب أن يكون أكبر من الصفر.")
        if locked_student.credit_balance < amount:
            raise ValidationError(f"رصيد الطالب الدائن ({locked_student.credit_balance}) غير كافٍ لسداد المبلغ المطلوب ({amount}).")
        if locked_invoice.remaining_amount < amount:
            raise ValidationError(f"المبلغ المطلوب سداده ({amount}) يتجاوز المتبقي على الفاتورة ({locked_invoice.remaining_amount}).")

        bal_before = locked_student.credit_balance
        bal_after = bal_before - amount
        locked_student.credit_balance = bal_after
        locked_student.save(update_fields=["credit_balance"])

        locked_invoice.paid_amount += amount
        if locked_invoice.remaining_amount <= Decimal("0.00"):
            locked_invoice.status = StudentInvoice.Status.PAID
        else:
            locked_invoice.status = StudentInvoice.Status.PARTIAL
        locked_invoice.save(update_fields=["paid_amount", "status", "updated_at"])

        # The schema has a single source_receipt FK, so we can guarantee provenance
        # only when there is exactly one active deposit source for this student.
        # Pooled balances must remain unlinked until a multi-source allocation ledger exists.
        src_receipt = None
        deposits = list(StudentCreditTransaction.objects.filter(
            student=locked_student,
            transaction_type=StudentCreditTransaction.TransactionType.DEPOSIT,
            is_reversed=False,
            receipt__isnull=False,
        ).order_by("created_at", "pk"))
        if len(deposits) == 1:
            deposit = deposits[0]
            from django.db.models import Sum
            consumed = StudentCreditTransaction.objects.filter(
                student=locked_student,
                transaction_type=StudentCreditTransaction.TransactionType.USAGE,
                source_receipt=deposit.receipt,
                is_reversed=False,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            if deposit.amount - consumed >= amount:
                src_receipt = deposit.receipt

        tx = StudentCreditTransaction.objects.create(
            school=locked_student.school,
            student=locked_student,
            transaction_type=StudentCreditTransaction.TransactionType.USAGE,
            amount=amount,
            balance_before=bal_before,
            balance_after=bal_after,
            invoice=locked_invoice,
            source_receipt=src_receipt,
            created_by=user,
            notes=f"سداد الفاتورة #{locked_invoice.invoice_number} من الرصيد الدائن للطالب",
        )

        from apps.accounting.services.auto_posting import post_credit_settlement_to_journal
        post_credit_settlement_to_journal(tx)
        return tx


def reverse_credit_usage(usage_tx: StudentCreditTransaction, reason: str, reversed_by=None) -> StudentCreditTransaction:
    """
    عكس حركة استخدام رصيد دائن لسداد فاتورة:
    إلغاء السداد من الفاتورة، إعادة الرصيد للطالب، ومنع العكس المكرر، وعكس قيد التسوية المحاسبي.
    """
    if usage_tx.is_reversed:
        raise ValidationError("تم عكس حركة استخدام الرصيد الدائن مسبقاً ولا يجوز عكسها أكثر من مرة.")
    if usage_tx.transaction_type != StudentCreditTransaction.TransactionType.USAGE:
        raise ValidationError("الحركة المحددة ليست حركة استخدام رصيد دائن.")
    
    from django.db import transaction
    with transaction.atomic():
        locked_tx = StudentCreditTransaction.objects.select_for_update().get(pk=usage_tx.pk)
        if locked_tx.is_reversed:
            raise ValidationError("تم عكس حركة استخدام الرصيد الدائن مسبقاً ولا يجوز عكسها أكثر من مرة.")

        locked_student = type(locked_tx.student).objects.select_for_update().get(pk=locked_tx.student_id)
        
        # Restore invoice balance
        if locked_tx.invoice:
            inv = StudentInvoice.objects.select_for_update().get(pk=locked_tx.invoice_id)
            inv.paid_amount = max(Decimal("0.00"), inv.paid_amount - locked_tx.amount)
            if inv.paid_amount == Decimal("0.00"):
                inv.status = StudentInvoice.Status.UNPAID
            else:
                inv.status = StudentInvoice.Status.PARTIAL
            inv.save(update_fields=["paid_amount", "status", "updated_at"])

        # Restore student credit balance
        bal_before = locked_student.credit_balance
        bal_after = bal_before + locked_tx.amount
        locked_student.credit_balance = bal_after
        locked_student.save(update_fields=["credit_balance"])

        # Create offsetting transaction in credit transactions
        reversal_tx = StudentCreditTransaction.objects.create(
            school=locked_student.school,
            student=locked_student,
            transaction_type=StudentCreditTransaction.TransactionType.ADJUSTMENT,
            amount=locked_tx.amount,
            balance_before=bal_before,
            balance_after=bal_after,
            invoice=locked_tx.invoice,
            created_by=reversed_by,
            notes=f"عكس حركة استخدام رصيد دائن #{locked_tx.id}: {reason}",
        )

        locked_tx.is_reversed = True
        locked_tx.reversed_by_transaction = reversal_tx
        locked_tx.save(update_fields=["is_reversed", "reversed_by_transaction", "updated_at"])

        # Reverse the journal entry for this settlement
        from apps.accounting.models import JournalEntry
        from apps.accounting.services.auto_posting import reverse_journal_entry
        settle_entry = JournalEntry.objects.filter(
            school=locked_student.school,
            source_module="student_fees_credit",
            source_reference=str(locked_tx.id),
            is_reversed=False,
            is_archived=False,
        ).first()
        if settle_entry:
            reverse_journal_entry(
                settle_entry,
                reason=f"عكس قيد تسوية رصيد دائن #{locked_tx.id}: {reason}",
                reversed_by=reversed_by,
            )

        return reversal_tx


def reverse_payment_receipt(receipt: PaymentReceipt, reason: str, reversed_by=None) -> PaymentReceipt:
    """
    العكس المحاسبي والتشغيلي الموحد لسند القبض المالي.
    يعكس التخصيصات، ويعيد الرصيد للفواتير والأقساط، ويخصم الفائض من رصيد الطالب
    مع معالجة أي استخدامات تابعة للرصيد الدائن وعكس قيود التسوية،
    وينشئ قيداً عكسياً مرتبطاً بالقيد الأصلي.
    """
    if receipt.is_cancelled:
        raise ValidationError("سند القبض ملغى أو معكوس مسبقاً.")

    from django.db import transaction
    with transaction.atomic():
        locked_receipt = PaymentReceipt.objects.select_for_update().get(pk=receipt.pk)
        if locked_receipt.is_cancelled:
            raise ValidationError("سند القبض ملغى أو معكوس مسبقاً.")

        allocations = list(locked_receipt.allocations.filter(
            status=PaymentAllocation.Status.ACTIVE
        ))

        for alloc in allocations:
            inv = alloc.invoice
            if inv:
                inv = StudentInvoice.objects.select_for_update().get(pk=inv.pk)
                inv.paid_amount = max(Decimal("0.00"), inv.paid_amount - alloc.allocated_amount)
                if inv.paid_amount == Decimal("0.00"):
                    inv.status = StudentInvoice.Status.UNPAID
                else:
                    inv.status = StudentInvoice.Status.PARTIAL
                inv.save(update_fields=["paid_amount", "status", "updated_at"])

            inst = alloc.installment
            if inst:
                inst = FeeInstallment.objects.select_for_update().get(pk=inst.pk)
                inst.paid_amount = max(Decimal("0.00"), inst.paid_amount - alloc.allocated_amount)
                if inst.paid_amount == Decimal("0.00"):
                    inst.status = FeeInstallment.Status.PENDING
                else:
                    inst.status = FeeInstallment.Status.PARTIAL
                inst.save(update_fields=["paid_amount", "status", "updated_at"])

            alloc.status = PaymentAllocation.Status.REVERSED
            alloc.notes = f"{alloc.notes} | تم العكس لسبب: {reason}".strip(" |")
            alloc.save(update_fields=["status", "notes", "updated_at"])

        # Reverse excess student credit if any. First unwind transactions with an
        # explicit source link. If historical pooled usages have no source, stop safely
        # instead of reversing an unrelated invoice based on timestamps.
        deposit_txs = list(locked_receipt.credit_transactions.filter(
            transaction_type=StudentCreditTransaction.TransactionType.DEPOSIT,
            is_reversed=False,
        ))
        total_excess = sum((tx.amount for tx in deposit_txs), Decimal("0.00"))
        if total_excess > Decimal("0.00"):
            student = type(locked_receipt.student).objects.select_for_update().get(
                pk=locked_receipt.student_id
            )
            if deposit_txs:
                first_deposit_at = min(tx.created_at for tx in deposit_txs)
                ambiguous_usages = StudentCreditTransaction.objects.filter(
                    student=student,
                    transaction_type=StudentCreditTransaction.TransactionType.USAGE,
                    source_receipt__isnull=True,
                    is_reversed=False,
                    created_at__gte=first_deposit_at,
                )
                if ambiguous_usages.exists():
                    raise ValidationError(
                        "لا يمكن عكس فائض هذا السند بأمان لوجود استخدامات رصيد قديمة غير مرتبطة بسند مصدر. "
                        "يجب تسوية هذه الاستخدامات أو ربطها بمصادرها قبل إلغاء السند؛ لم يتم عكس أي فاتورة أخرى."
                    )

            usage_txs = list(StudentCreditTransaction.objects.select_for_update().filter(
                student=student,
                transaction_type=StudentCreditTransaction.TransactionType.USAGE,
                source_receipt=locked_receipt,
                is_reversed=False,
            ).order_by("-created_at", "-pk"))

            for usage_tx in usage_txs:
                reverse_credit_usage(
                    usage_tx,
                    reason=f"عكس تتابعي بسبب إلغاء سند القبض #{locked_receipt.receipt_number}",
                    reversed_by=reversed_by,
                )

            student.refresh_from_db()
            if student.credit_balance < total_excess:
                raise ValidationError(
                    f"لا يمكن عكس سند القبض #{locked_receipt.receipt_number}: الرصيد المتاح "
                    f"({student.credit_balance}) أقل من فائض السند المطلوب عكسه ({total_excess})."
                )

            bal_before = student.credit_balance
            bal_after = bal_before - total_excess
            student.credit_balance = bal_after
            student.save(update_fields=["credit_balance"])

            for dep in deposit_txs:
                dep.is_reversed = True
                dep.save(update_fields=["is_reversed", "updated_at"])

            StudentCreditTransaction.objects.create(
                school=locked_receipt.school,
                student=student,
                transaction_type=StudentCreditTransaction.TransactionType.REFUND,
                amount=total_excess,
                balance_before=bal_before,
                balance_after=bal_after,
                receipt=locked_receipt,
                created_by=reversed_by,
                notes=f"عكس فائض الرصيد الدائن بسبب إلغاء سند القبض #{locked_receipt.receipt_number}: {reason}",
            )

        locked_receipt.is_cancelled = True
        locked_receipt.notes = f"{locked_receipt.notes} | ملغى/معكوس لسبب: {reason}".strip(" |")
        locked_receipt.save(update_fields=["is_cancelled", "notes", "updated_at"])

        if locked_receipt.journal_entry:
            from apps.accounting.services.auto_posting import reverse_journal_entry
            reverse_journal_entry(
                locked_receipt.journal_entry,
                reason=f"عكس سند القبض #{locked_receipt.receipt_number}: {reason}",
                reversed_by=reversed_by,
            )

        return locked_receipt


class PaymentAllocation(TenantOwnedModel):
    """دفتر تخصيص سندات القبض والدفعات على الفواتير والأقساط الفردية."""
    class Status(models.TextChoices):
        ACTIVE = "active", "نشط ومعتمد"
        REVERSED = "reversed", "معكوس / مسترد"

    receipt = models.ForeignKey(
        PaymentReceipt,
        verbose_name="سند القبض",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة المخصصة",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    installment = models.ForeignKey(
        "FeeInstallment",
        verbose_name="القسط المالي (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allocations",
    )
    allocated_amount = models.DecimalField("المبلغ المخصص", max_digits=12, decimal_places=2)
    allocated_at = models.DateTimeField("تاريخ التخصيص", default=timezone.now)
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المستخدم المخصص",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fee_allocations",
    )
    status = models.CharField("حالة التخصيص", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.CharField("ملاحظات التخصيص", max_length=255, blank=True)

    class Meta:
        verbose_name = "تخصيص دفعة مالية"
        verbose_name_plural = "سجل تخصيص الدفعات على الفواتير والأقساط"

    def __str__(self) -> str:
        return f"{self.receipt.receipt_number} -> {self.invoice.invoice_number}: {self.allocated_amount}"


class FeeInstallmentPlan(TenantOwnedModel):
    """خطة تقسيط الرسوم الدراسية المعتمدة للطالب."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="installment_plans",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        verbose_name="الفاتورة المرتبطة",
        on_delete=models.CASCADE,
        related_name="installment_plans",
    )
    plan_name = models.CharField("اسم خطة التقسيط (مثال: تقسيط ربع سنوي)", max_length=150)
    total_amount = models.DecimalField("إجمالي مبلغ الخطة", max_digits=12, decimal_places=2)
    number_of_installments = models.PositiveSmallIntegerField("عدد الأقساط", default=3)
    notes = models.TextField("ملاحظات وشروط الاتفاق", blank=True)

    class Meta:
        verbose_name = "خطة تقسيط رسوم"
        verbose_name_plural = "خطط تقسيط الرسوم"

    def __str__(self) -> str:
        return f"{self.plan_name} - {self.student}: {self.total_amount}"


class FeeInstallment(TenantOwnedModel):
    """القسط الفردي ضمن خطة تقسيط رسوم الطالب."""
    class Status(models.TextChoices):
        PENDING = "pending", "مستحق (قيد السداد)"
        PARTIAL = "partially_paid", "مسدد جزئياً"
        PAID = "paid", "مسدد بالكامل"
        OVERDUE = "overdue", "متأخر عن موعد الاستحقاق"

    plan = models.ForeignKey(
        FeeInstallmentPlan,
        verbose_name="خطة التقسيط",
        on_delete=models.CASCADE,
        related_name="installments",
    )
    installment_number = models.PositiveSmallIntegerField("رقم القسط (1, 2, 3...)")
    title = models.CharField("بيان القسط (مثل: قسط شهر نوفمبر)", max_length=150)
    amount = models.DecimalField("مبلغ القسط", max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField("المبلغ المسدد", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    due_date = models.DateField("تاريخ الاستحقاق")
    paid_date = models.DateField("تاريخ السداد الفعلي", null=True, blank=True)
    status = models.CharField("حالة القسط", max_length=20, choices=Status.choices, default=Status.PENDING)
    receipt = models.ForeignKey(
        PaymentReceipt,
        verbose_name="سند السداد المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installments",
    )

    class Meta:
        verbose_name = "قسط مالي مجدول"
        verbose_name_plural = "الأقساط المالية المجدولة"
        ordering = ["due_date", "installment_number"]

    def __str__(self) -> str:
        return f"قسط #{self.installment_number} ({self.title}) - {self.amount} [{self.get_status_display()}]"

    @property
    def remaining_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.amount - self.paid_amount)
