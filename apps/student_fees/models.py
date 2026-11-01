"""Student fees, invoicing, installment plans, and payment receipt domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


def _save_student_credit_balance(student) -> None:
    """Persist a balance only from a student-fees ledger transaction."""
    student._allow_credit_balance_update = True
    try:
        student.save(update_fields=["credit_balance"])
    finally:
        del student._allow_credit_balance_update


def _inherit_branch(instance, source) -> None:
    """Validate school ownership and inherit any branch-specific related record."""
    if source is None:
        return
    if source.school_id != instance.school_id:
        raise ValidationError("السجل المرتبط لا يتبع المدرسة نفسها.")
    if source.branch_id:
        if not instance.branch_id:
            instance.branch_id = source.branch_id
        elif instance.branch_id != source.branch_id:
            raise ValidationError("السجل المرتبط يتبع فرعاً مختلفاً.")


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
                condition=models.Q(is_archived=False, branch__isnull=True),
                name="student_fees_structure_global_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "branch", "academic_year", "grade_level", "fee_category"],
                condition=models.Q(is_archived=False, branch__isnull=False),
                name="student_fees_structure_branch_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.grade_level.name} - {self.fee_category.name}: {self.amount}"

    def clean(self):
        super().clean()
        related = (
            ("academic_year", self.academic_year_id, self.academic_year),
            ("grade_level", self.grade_level_id, self.grade_level),
            ("fee_category", self.fee_category_id, self.fee_category),
        )
        for field, field_id, obj in related:
            if field_id and obj.school_id != self.school_id:
                raise ValidationError({field: "السجل المرتبط لا يتبع المدرسة نفسها."})
            related_branch = getattr(obj, "branch_id", None) if field_id else None
            if related_branch and related_branch != self.branch_id:
                raise ValidationError({field: "السجل الأكاديمي يتبع فرعاً مختلفاً عن هيكل الرسوم."})
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "قيمة هيكل الرسوم يجب أن تكون أكبر من الصفر."})


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
    idempotency_key = models.CharField("مفتاح منع تكرار إنشاء الفاتورة", max_length=128, blank=True)
    total_amount = models.DecimalField("إجمالي قيمة الفاتورة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField("إجمالي الخصومات والمنح", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField("المبلغ المسدد حتى الآن", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة الفاتورة", max_length=20, choices=Status.choices, default=Status.UNPAID)
    issue_date = models.DateField("تاريخ إصدار الفاتورة", default=timezone.localdate)
    due_date = models.DateField("تاريخ الاستحقاق")
    notes = models.TextField("ملاحظات الفاتورة", blank=True)
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
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="student_fees_invoice_idempotency_uniq",
            ),
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

    def save(self, *args, **kwargs):
        if self._state.adding and self.student_id:
            _inherit_branch(self, self.student)
            if self.academic_year_id:
                _inherit_branch(self, self.academic_year)
            if self.student.branch_id != self.branch_id:
                raise ValidationError("فاتورة الطالب يجب أن تتبع فرع الطالب نفسه.")
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.student_id:
            _inherit_branch(self, self.student)
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.student_id and self.student.branch_id != self.branch_id:
            raise ValidationError({"branch": "فاتورة الطالب يجب أن تتبع فرع الطالب نفسه."})
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة نفسها."})
        if self.academic_year_id and self.academic_year.branch_id and self.academic_year.branch_id != self.branch_id:
            raise ValidationError({"academic_year": "السنة الدراسية تتبع فرعاً مختلفاً."})
        if self.discount_amount < Decimal("0.00"):
            raise ValidationError({"discount_amount": "لا يمكن أن يكون الخصم سالباً."})
        if self.total_amount < Decimal("0.00"):
            raise ValidationError({"total_amount": "إجمالي الفاتورة لا يمكن أن يكون سالباً."})
        if self.total_amount > Decimal("0.00") and self.discount_amount > self.total_amount:
            raise ValidationError({"discount_amount": "لا يمكن أن يتجاوز الخصم إجمالي الفاتورة."})
        if self.paid_amount < Decimal("0.00"):
            raise ValidationError({"paid_amount": "المبلغ المسدد لا يمكن أن يكون سالباً."})

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

    def save(self, *args, **kwargs):
        if self._state.adding and self.invoice_id:
            _inherit_branch(self, self.invoice)
            if self.fee_category_id:
                _inherit_branch(self, self.fee_category)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.invoice_id:
            _inherit_branch(self, self.invoice)
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "الفاتورة لا تتبع المدرسة نفسها."})
        if self.invoice_id and self.invoice.branch_id != self.branch_id:
            raise ValidationError({"branch": "بند الفاتورة يجب أن يتبع فرع الفاتورة."})
        if self.fee_category_id and self.fee_category.school_id != self.school_id:
            raise ValidationError({"fee_category": "بند الرسوم لا يتبع المدرسة نفسها."})
        if self.invoice_id and self.fee_category_id:
            if self.invoice.school_id != self.fee_category.school_id:
                raise ValidationError("لا يمكن ربط بند رسوم من مدرسة أخرى بالفاتورة.")
            if self.fee_category.branch_id and self.fee_category.branch_id != self.invoice.branch_id:
                raise ValidationError("بند الرسوم يتبع فرعاً مختلفاً عن الفاتورة.")
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "قيمة بند الفاتورة يجب أن تكون أكبر من الصفر."})
        if self.discount_amount < Decimal("0.00") or self.discount_amount > self.amount:
            raise ValidationError({"discount_amount": "خصم البند يجب أن يكون بين صفر وقيمة البند."})


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
    idempotency_key = models.CharField("مفتاح منع تكرار العملية", max_length=128, blank=True)
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
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="student_fees_receipt_idempotency_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "paid_at"]),
            models.Index(fields=["school", "student"]),
        ]

    def __str__(self) -> str:
        return f"سند #{self.receipt_number} - {self.student}: {self.amount} ({self.get_payment_method_display()})"

    def clean(self):
        super().clean()
        if self.student_id:
            _inherit_branch(self, self.student)
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "مبلغ سند القبض يجب أن يكون أكبر من الصفر."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا ينتمي إلى نفس المدرسة."})
        if self.student_id and self.student.branch_id != self.branch_id:
            raise ValidationError({"branch": "سند القبض يجب أن يتبع فرع الطالب نفسه."})
        if self.invoice_id:
            if self.invoice.school_id != self.school_id:
                raise ValidationError({"invoice": "الفاتورة المحددة لا تتبع نفس المدرسة."})
            if self.invoice.branch_id != self.branch_id:
                raise ValidationError({"invoice": "الفاتورة تتبع فرعاً مختلفاً عن سند القبض."})
            if self.invoice.student_id != self.student_id:
                raise ValidationError({"invoice": "الفاتورة المحددة لا تخص هذا الطالب."})
            if self.invoice.status == StudentInvoice.Status.CANCELLED:
                raise ValidationError({"invoice": "لا يمكن سداد أو ربط سند بفاتورة ملغاة."})

    def save(self, *args, **kwargs):
        if is_new and self.student_id:
            _inherit_branch(self, self.student)
            if self.invoice_id:
                _inherit_branch(self, self.invoice)
        is_new = self._state.adding
        from django.db import transaction
        if not is_new:
            original = type(self).objects.filter(pk=self.pk).values(
                "school_id", "branch_id", "student_id", "invoice_id",
                "receipt_number", "amount", "payment_method",
                "reference_number", "paid_at", "received_by_id",
                "idempotency_key",
            ).first()
            if original:
                changed = [
                    field for field in original
                    if original[field] != getattr(self, field)
                ]
                if changed:
                    raise ValidationError(
                        "سند القبض سجل مالي غير قابل لتغيير بياناته بعد الإنشاء؛ "
                        "استخدم إجراء العكس ثم أنشئ سنداً صحيحاً."
                    )
        with transaction.atomic():
            locked_student = None
            if is_new:
                from apps.students.models import Student
                locked_student = Student.objects.select_for_update().get(
                    pk=self.student_id, school_id=self.school_id,
                )
                self.student = locked_student
                if self.invoice_id:
                    self.invoice = StudentInvoice.objects.select_for_update().get(
                        pk=self.invoice_id, school_id=self.school_id,
                    )
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
                                    branch=self.branch,
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
                                branch=self.branch,
                                receipt=self,
                                invoice=inv,
                                installment=None,
                                allocated_amount=pay_part,
                                allocated_by=self.received_by,
                                notes="تخصيص مباشر للفاتورة المحددة بالسند",
                            )
                        elif rem_for_inst > Decimal("0.00"):
                            PaymentAllocation.objects.create(
                                school=self.school,
                                branch=self.branch,
                                receipt=self,
                                invoice=inv,
                                installment=None,
                                allocated_amount=rem_for_inst,
                                allocated_by=self.received_by,
                                notes="تخصيص المتبقي من دفعة الفاتورة بعد الأقساط",
                            )

                    excess = self.amount - pay_part
                    if excess > Decimal("0.00"):
                        student = locked_student
                        bal_before = student.credit_balance
                        bal_after = bal_before + excess
                        student.credit_balance = bal_after
                        _save_student_credit_balance(student)

                        StudentCreditTransaction.objects.create(
                            school=self.school,
                            branch=self.branch,
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
                                    branch=self.branch,
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
                                branch=self.branch,
                                receipt=self,
                                invoice=inv,
                                installment=None,
                                allocated_amount=pay_part,
                                allocated_by=self.received_by,
                                notes="تخصيص آلي حسب تاريخ الاستحقاق",
                            )
                        elif rem_for_inst > Decimal("0.00"):
                            PaymentAllocation.objects.create(
                                school=self.school,
                                branch=self.branch,
                                receipt=self,
                                invoice=inv,
                                installment=None,
                                allocated_amount=rem_for_inst,
                                allocated_by=self.received_by,
                                notes="تخصيص المتبقي من الدفعة بعد الأقساط",
                            )

                    # If student paid more than all open invoices, credit the excess to their credit_balance
                    if remaining > Decimal("0.00"):
                        student = locked_student
                        bal_before = student.credit_balance
                        bal_after = bal_before + remaining
                        student.credit_balance = bal_after
                        _save_student_credit_balance(student)

                        StudentCreditTransaction.objects.create(
                            school=self.school,
                            branch=self.branch,
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
    refund_payment_method = models.CharField(
        "طريقة صرف الاسترداد", max_length=20,
        choices=PaymentReceipt.PaymentMethod.choices, blank=True,
    )
    refund_reference = models.CharField("مرجع عملية الاسترداد", max_length=100, blank=True)
    idempotency_key = models.CharField("مفتاح منع تكرار الاسترداد", max_length=128, blank=True)

    class Meta:
        verbose_name = "حركة رصيد دائن لطالب"
        verbose_name_plural = "دفتر الأرصدة الدائنة للطلاب"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="student_credit_idempotency_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.get_transaction_type_display()}: {self.amount} (الرصيد: {self.balance_after})"

    def save(self, *args, **kwargs):
        if self._state.adding and self.student_id:
            _inherit_branch(self, self.student)
            for field in ("invoice", "receipt", "source_receipt"):
                related = getattr(self, field, None)
                if related is not None:
                    _inherit_branch(self, related)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.student_id:
            _inherit_branch(self, self.student)
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "قيمة حركة الرصيد يجب أن تكون أكبر من الصفر."})
        if self.balance_before < Decimal("0.00") or self.balance_after < Decimal("0.00"):
            raise ValidationError("لا يمكن أن يكون رصيد الطالب الدائن سالباً.")
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة نفسها."})
        if self.student_id and self.student.branch_id != self.branch_id:
            raise ValidationError({"branch": "حركة رصيد الطالب يجب أن تتبع فرع الطالب نفسه."})
        for field in ("invoice", "receipt", "source_receipt"):
            obj = getattr(self, field, None)
            if obj is not None and obj.school_id != self.school_id:
                raise ValidationError({field: "السجل المرتبط لا يتبع المدرسة نفسها."})
            if obj is not None and obj.branch_id != self.branch_id:
                raise ValidationError({field: "السجل المرتبط يتبع فرعاً مختلفاً."})
        if self.invoice_id and self.invoice.student_id != self.student_id:
            raise ValidationError({"invoice": "الفاتورة لا تخص الطالب المحدد."})
        for field in ("receipt", "source_receipt"):
            obj = getattr(self, field, None)
            if obj is not None and obj.student_id != self.student_id:
                raise ValidationError({field: "سند القبض لا يخص الطالب المحدد."})


def apply_credit_balance_to_invoice(
    student, invoice: StudentInvoice, amount: Decimal | None = None,
    user=None, idempotency_key: str = "",
) -> StudentCreditTransaction:
    """استخدام الرصيد الدائن للطالب لسداد فاتورة مستحقة وتوثيق العملية في دفتر الأرصدة الدائنة وإثبات قيد التسوية."""
    from django.db import transaction
    if invoice.school_id != student.school_id:
        raise ValidationError("الفاتورة والطالب لا يتبعان لنفس المدرسة.")
    if invoice.student_id != student.pk:
        raise ValidationError("الفاتورة المحددة لا تخص هذا الطالب.")

    with transaction.atomic():
        from apps.tenants.models import School
        School.objects.select_for_update().get(pk=student.school_id)
        locked_student = type(student).objects.select_for_update().get(pk=student.pk)
        locked_invoice = StudentInvoice.objects.select_for_update().get(pk=invoice.pk)

        if amount is None:
            amount = min(locked_student.credit_balance, locked_invoice.remaining_amount)
        amount = Decimal(amount)
        if idempotency_key:
            existing = StudentCreditTransaction.objects.filter(
                school=locked_student.school,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                if (
                    existing.transaction_type != StudentCreditTransaction.TransactionType.USAGE
                    or existing.student_id != locked_student.pk
                    or existing.invoice_id != locked_invoice.pk
                    or existing.branch_id != locked_invoice.branch_id
                    or existing.amount != amount
                ):
                    raise ValidationError("مفتاح منع التكرار مستخدم لعملية استخدام رصيد مختلفة.")
                if existing.is_reversed:
                    raise ValidationError("سبق عكس العملية المرتبطة بهذا المفتاح؛ استخدم مفتاحاً جديداً.")
                return existing
        if amount <= Decimal("0.00"):
            raise ValidationError("المبلغ المطلوب استخدامه من الرصيد الدائن يجب أن يكون أكبر من الصفر.")
        if locked_student.credit_balance < amount:
            raise ValidationError(f"رصيد الطالب الدائن ({locked_student.credit_balance}) غير كافٍ لسداد المبلغ المطلوب ({amount}).")
        if locked_invoice.remaining_amount < amount:
            raise ValidationError(f"المبلغ المطلوب سداده ({amount}) يتجاوز المتبقي على الفاتورة ({locked_invoice.remaining_amount}).")

        bal_before = locked_student.credit_balance
        bal_after = bal_before - amount
        locked_student.credit_balance = bal_after
        _save_student_credit_balance(locked_student)

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
            branch=locked_invoice.branch,
            student=locked_student,
            transaction_type=StudentCreditTransaction.TransactionType.USAGE,
            amount=amount,
            balance_before=bal_before,
            balance_after=bal_after,
            invoice=locked_invoice,
            source_receipt=src_receipt,
            idempotency_key=idempotency_key,
            created_by=user,
            notes=f"سداد الفاتورة #{locked_invoice.invoice_number} من الرصيد الدائن للطالب",
        )

        remaining_for_installments = amount
        plan = locked_invoice.installment_plans.filter(is_archived=False).first()
        if plan:
            installments = plan.installments.filter(
                status__in=[
                    FeeInstallment.Status.PENDING,
                    FeeInstallment.Status.PARTIAL,
                    FeeInstallment.Status.OVERDUE,
                ],
                is_archived=False,
            ).order_by("due_date", "installment_number").select_for_update()
            for installment in installments:
                if remaining_for_installments <= Decimal("0.00"):
                    break
                part = min(remaining_for_installments, installment.remaining_amount)
                if part <= Decimal("0.00"):
                    continue
                installment.paid_amount += part
                installment.status = (
                    FeeInstallment.Status.PAID
                    if installment.paid_amount >= installment.amount
                    else FeeInstallment.Status.PARTIAL
                )
                installment.paid_date = timezone.localdate()
                installment.save(update_fields=[
                    "paid_amount", "status", "paid_date", "updated_at",
                ])
                PaymentAllocation.objects.create(
                    school=locked_student.school,
                    branch=locked_invoice.branch,
                    credit_transaction=tx,
                    invoice=locked_invoice,
                    installment=installment,
                    allocated_amount=part,
                    allocated_by=user,
                    notes="تخصيص استخدام الرصيد الدائن على القسط",
                )
                remaining_for_installments -= part
        if remaining_for_installments > Decimal("0.00"):
            PaymentAllocation.objects.create(
                school=locked_student.school,
                branch=locked_invoice.branch,
                credit_transaction=tx,
                invoice=locked_invoice,
                allocated_amount=remaining_for_installments,
                allocated_by=user,
                notes="تخصيص استخدام الرصيد الدائن على الفاتورة",
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

        for allocation in locked_tx.allocations.select_for_update().filter(
            status=PaymentAllocation.Status.ACTIVE,
        ):
            if allocation.installment_id:
                installment = FeeInstallment.objects.select_for_update().get(
                    pk=allocation.installment_id,
                )
                installment.paid_amount = max(
                    Decimal("0.00"), installment.paid_amount - allocation.allocated_amount,
                )
                installment.status = (
                    (
                        FeeInstallment.Status.OVERDUE
                        if installment.due_date < timezone.localdate()
                        else FeeInstallment.Status.PENDING
                    )
                    if installment.paid_amount == Decimal("0.00")
                    else FeeInstallment.Status.PARTIAL
                )
                if installment.paid_amount == Decimal("0.00"):
                    installment.paid_date = None
                installment.save(update_fields=[
                    "paid_amount", "status", "paid_date", "updated_at",
                ])
            allocation.status = PaymentAllocation.Status.REVERSED
            allocation.notes = f"{allocation.notes} | عكس: {reason}"[:255]
            allocation.save(update_fields=["status", "notes", "updated_at"])

        # Restore student credit balance
        bal_before = locked_student.credit_balance
        bal_after = bal_before + locked_tx.amount
        locked_student.credit_balance = bal_after
        _save_student_credit_balance(locked_student)

        # Create offsetting transaction in credit transactions
        reversal_branch = (
            locked_tx.invoice.branch if locked_tx.invoice_id
            else locked_student.branch
        )
        reversal_tx = StudentCreditTransaction.objects.create(
            school=locked_student.school,
            branch=reversal_branch,
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
                    inst.status = (
                        FeeInstallment.Status.OVERDUE
                        if inst.due_date < timezone.localdate()
                        else FeeInstallment.Status.PENDING
                    )
                else:
                    inst.status = FeeInstallment.Status.PARTIAL
                # Keep the legacy single-receipt pointer aligned with the
                # remaining active receipt allocations after this reversal.
                remaining_allocation = inst.allocations.filter(
                    status=PaymentAllocation.Status.ACTIVE,
                    receipt__isnull=False,
                ).exclude(receipt=locked_receipt).order_by("-allocated_at").first()
                inst.receipt = remaining_allocation.receipt if remaining_allocation else None
                inst.save(update_fields=[
                    "paid_amount", "status", "receipt", "updated_at",
                ])

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
            _save_student_credit_balance(student)

            for dep in deposit_txs:
                dep.is_reversed = True
                dep.save(update_fields=["is_reversed", "updated_at"])

            StudentCreditTransaction.objects.create(
                school=locked_receipt.school,
                branch=locked_receipt.branch,
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
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    credit_transaction = models.ForeignKey(
        StudentCreditTransaction,
        verbose_name="حركة استخدام الرصيد الدائن",
        null=True,
        blank=True,
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
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(receipt__isnull=False, credit_transaction__isnull=True)
                    | models.Q(receipt__isnull=True, credit_transaction__isnull=False)
                ),
                name="student_fees_allocation_one_source",
            )
        ]

    def __str__(self) -> str:
        source = self.receipt.receipt_number if self.receipt_id else str(self.credit_transaction_id)
        return f"{source} -> {self.invoice.invoice_number}: {self.allocated_amount}"

    def save(self, *args, **kwargs):
        if self._state.adding and self.invoice_id:
            _inherit_branch(self, self.invoice)
            for field in ("receipt", "credit_transaction", "installment"):
                related = getattr(self, field, None)
                if related is not None:
                    _inherit_branch(self, related)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.invoice_id:
            _inherit_branch(self, self.invoice)
        if self.allocated_amount <= Decimal("0.00"):
            raise ValidationError({"allocated_amount": "قيمة التخصيص يجب أن تكون أكبر من الصفر."})
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "الفاتورة لا تتبع المدرسة نفسها."})
        if self.invoice_id and self.invoice.branch_id != self.branch_id:
            raise ValidationError({"branch": "التخصيص يجب أن يتبع فرع الفاتورة."})
        if self.receipt_id and self.receipt.school_id != self.school_id:
            raise ValidationError({"receipt": "سند القبض لا يتبع المدرسة نفسها."})
        if self.credit_transaction_id and self.credit_transaction.school_id != self.school_id:
            raise ValidationError({"credit_transaction": "حركة الرصيد لا تتبع المدرسة نفسها."})
        if self.receipt_id:
            if self.receipt.student_id != self.invoice.student_id:
                raise ValidationError("سند القبض والفاتورة لا يخصان الطالب نفسه.")
            if self.receipt.branch_id != self.branch_id:
                raise ValidationError("سند القبض يتبع فرعاً مختلفاً عن تخصيص الفاتورة.")
        if self.credit_transaction_id:
            if self.credit_transaction.branch_id != self.branch_id:
                raise ValidationError("حركة الرصيد تتبع فرعاً مختلفاً عن تخصيص الفاتورة.")
            if self.credit_transaction.student_id != self.invoice.student_id:
                raise ValidationError("حركة الرصيد والفاتورة لا تخصان الطالب نفسه.")
            if self.credit_transaction.invoice_id != self.invoice_id:
                raise ValidationError("الفاتورة لا تطابق فاتورة حركة الرصيد.")
        if self.installment_id:
            if self.installment.plan.invoice_id != self.invoice_id:
                raise ValidationError("القسط المحدد لا يتبع الفاتورة نفسها.")
            if self.installment.plan.student_id != self.invoice.student_id:
                raise ValidationError("القسط المحدد لا يخص الطالب صاحب الفاتورة.")


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

    def save(self, *args, **kwargs):
        if self._state.adding and self.invoice_id:
            _inherit_branch(self, self.invoice)
            if self.student_id:
                _inherit_branch(self, self.student)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.invoice_id:
            _inherit_branch(self, self.invoice)
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة نفسها."})
        if self.student_id and self.student.branch_id != self.branch_id:
            raise ValidationError({"branch": "خطة التقسيط يجب أن تتبع فرع الطالب نفسه."})
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "الفاتورة لا تتبع المدرسة نفسها."})
        if self.invoice_id and self.student_id and self.invoice.student_id != self.student_id:
            raise ValidationError({"student": "خطة التقسيط والطالب لا يخصان الفاتورة نفسها."})
        if self.invoice_id and self.invoice.branch_id != self.branch_id:
            raise ValidationError({"branch": "خطة التقسيط يجب أن تتبع فرع الفاتورة."})
        if self.total_amount <= Decimal("0.00"):
            raise ValidationError({"total_amount": "إجمالي خطة التقسيط يجب أن يكون أكبر من الصفر."})
        if self.number_of_installments < 1:
            raise ValidationError({"number_of_installments": "يجب أن تحتوي خطة التقسيط على قسط واحد على الأقل."})


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

    def save(self, *args, **kwargs):
        if self._state.adding and self.plan_id:
            _inherit_branch(self, self.plan)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.plan_id:
            _inherit_branch(self, self.plan)
        if self.plan_id and self.plan.school_id != self.school_id:
            raise ValidationError({"plan": "خطة التقسيط لا تتبع المدرسة نفسها."})
        if self.plan_id and self.plan.branch_id != self.branch_id:
            raise ValidationError({"branch": "القسط يجب أن يتبع فرع خطة التقسيط."})
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "قيمة القسط يجب أن تكون أكبر من الصفر."})
        if self.paid_amount < Decimal("0.00") or self.paid_amount > self.amount:
            raise ValidationError({"paid_amount": "المبلغ المسدد يجب أن يكون بين صفر وقيمة القسط."})


class FeeDiscountPolicy(TenantOwnedModel):
    """حدود الخصومات والإعفاءات المعتمدة على مستوى المدرسة."""
    max_discount_percent = models.DecimalField(
        "الحد الأعلى لنسبة الخصم", max_digits=5, decimal_places=2,
        default=Decimal("100.00"),
    )
    auto_approval_limit = models.DecimalField(
        "حد الاعتماد التلقائي", max_digits=12, decimal_places=2,
        default=Decimal("0.00"),
    )
    allow_full_exemption = models.BooleanField("السماح بالإعفاء الكامل", default=False)

    class Meta:
        verbose_name = "سياسة خصومات الرسوم"
        verbose_name_plural = "سياسات خصومات الرسوم"
        constraints = [
            models.UniqueConstraint(
                fields=["school"], condition=models.Q(is_archived=False),
                name="student_fee_discount_policy_school_uniq",
            )
        ]

    def clean(self):
        super().clean()
        if self.max_discount_percent < Decimal("0.00") or self.max_discount_percent > Decimal("100.00"):
            raise ValidationError({"max_discount_percent": "نسبة الحد الأعلى يجب أن تكون بين صفر و100."})
        if self.auto_approval_limit < Decimal("0.00"):
            raise ValidationError({"auto_approval_limit": "حد الاعتماد التلقائي لا يمكن أن يكون سالباً."})


class FeeDiscountRequest(TenantOwnedModel):
    """طلب خصم أو إعفاء موثق على فاتورة طالب."""
    class Status(models.TextChoices):
        PENDING = "pending", "بانتظار الاعتماد"
        APPROVED = "approved", "معتمد"
        REJECTED = "rejected", "مرفوض"

    invoice = models.ForeignKey(
        StudentInvoice, verbose_name="الفاتورة", on_delete=models.PROTECT,
        related_name="discount_requests",
    )
    idempotency_key = models.CharField("مفتاح منع تكرار طلب الخصم", max_length=128, blank=True)
    amount = models.DecimalField("قيمة الخصم المطلوب", max_digits=12, decimal_places=2)
    reason = models.TextField("مبرر الخصم أو الإعفاء")
    status = models.CharField("حالة الطلب", max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="مقدم الطلب",
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="student_fee_discount_requests",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="صاحب قرار الاعتماد",
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_student_fee_discounts",
    )
    decided_at = models.DateTimeField("وقت القرار", null=True, blank=True)
    decision_notes = models.TextField("ملاحظات القرار", blank=True)

    class Meta:
        verbose_name = "طلب خصم رسوم"
        verbose_name_plural = "طلبات خصومات وإعفاءات الرسوم"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "invoice"],
                condition=models.Q(status="pending", is_archived=False),
                name="student_fee_one_pending_discount_invoice",
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="student_fee_discount_idempotency_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["school", "status", "created_at"],
                name="st_fee_disc_school_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self._state.adding and self.invoice_id:
            _inherit_branch(self, self.invoice)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.invoice_id:
            _inherit_branch(self, self.invoice)
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "الفاتورة لا تتبع المدرسة نفسها."})
        if self.invoice_id and self.invoice.branch_id != self.branch_id:
            raise ValidationError({"branch": "طلب الخصم يجب أن يتبع فرع الفاتورة."})
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "قيمة الخصم يجب أن تكون أكبر من الصفر."})
        if not (self.reason or "").strip():
            raise ValidationError({"reason": "يجب توضيح سبب الخصم أو الإعفاء."})


def refund_student_credit(
    *, student, amount: Decimal, payment_method: str, reference: str = "",
    user=None, idempotency_key: str = "",
) -> StudentCreditTransaction:
    """صرف جزء من الرصيد الدائن للطالب مع قيد محاسبي وسجل تدقيق مالي."""
    from django.db import transaction
    with transaction.atomic():
        from apps.tenants.models import School
        School.objects.select_for_update().get(pk=student.school_id)
        locked_student = type(student).objects.select_for_update().get(pk=student.pk)
        amount = Decimal(amount)
        if idempotency_key:
            existing = StudentCreditTransaction.objects.filter(
                school=locked_student.school,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                if (
                    existing.transaction_type != StudentCreditTransaction.TransactionType.REFUND
                    or existing.student_id != locked_student.pk
                    or existing.branch_id != locked_student.branch_id
                    or existing.amount != amount
                    or existing.refund_payment_method != payment_method
                    or existing.refund_reference != reference
                ):
                    raise ValidationError("مفتاح منع التكرار مستخدم مسبقاً لبيانات استرداد مختلفة.")
                if existing.is_reversed:
                    raise ValidationError("سبق عكس الاسترداد المرتبط بهذا المفتاح؛ استخدم مفتاحاً جديداً.")
                return existing
        if amount <= Decimal("0.00"):
            raise ValidationError("قيمة الاسترداد يجب أن تكون أكبر من الصفر.")
        if amount > locked_student.credit_balance:
            raise ValidationError("قيمة الاسترداد تتجاوز الرصيد الدائن المتاح للطالب.")
        if payment_method not in PaymentReceipt.PaymentMethod.values:
            raise ValidationError("طريقة صرف الاسترداد غير معتمدة.")
        bal_before = locked_student.credit_balance
        bal_after = bal_before - amount
        locked_student.credit_balance = bal_after
        _save_student_credit_balance(locked_student)
        refund_tx = StudentCreditTransaction.objects.create(
            school=locked_student.school,
            branch=locked_student.branch,
            student=locked_student,
            transaction_type=StudentCreditTransaction.TransactionType.REFUND,
            amount=amount,
            balance_before=bal_before,
            balance_after=bal_after,
            refund_payment_method=payment_method,
            refund_reference=reference,
            idempotency_key=idempotency_key,
            created_by=user,
            notes="استرداد نقدي من الرصيد الدائن للطالب",
        )
        from apps.accounting.services.auto_posting import post_student_credit_refund_to_journal
        post_student_credit_refund_to_journal(refund_tx)
        return refund_tx


def reverse_credit_refund(
    refund_tx: StudentCreditTransaction, *, reason: str, reversed_by=None,
) -> StudentCreditTransaction:
    """عكس استرداد مستقل وإعادة المبلغ إلى رصيد الطالب دون تعديل الحركة الأصلية."""
    from django.db import transaction
    from apps.accounting.models import JournalEntry
    from apps.accounting.services.auto_posting import reverse_journal_entry
    with transaction.atomic():
        locked_tx = StudentCreditTransaction.objects.select_for_update().get(pk=refund_tx.pk)
        if locked_tx.transaction_type != StudentCreditTransaction.TransactionType.REFUND:
            raise ValidationError("الحركة المحددة ليست استرداداً.")
        if locked_tx.receipt_id:
            raise ValidationError("استرداد ناتج عن عكس سند قبض؛ يجب معالجة السند المصدر لا عكسه منفرداً.")
        if locked_tx.is_reversed:
            raise ValidationError("تم عكس هذا الاسترداد مسبقاً.")
        student = type(locked_tx.student).objects.select_for_update().get(pk=locked_tx.student_id)
        bal_before = student.credit_balance
        bal_after = bal_before + locked_tx.amount
        student.credit_balance = bal_after
        _save_student_credit_balance(student)
        reversal = StudentCreditTransaction.objects.create(
            school=student.school,
            branch=student.branch,
            student=student,
            transaction_type=StudentCreditTransaction.TransactionType.ADJUSTMENT,
            amount=locked_tx.amount,
            balance_before=bal_before,
            balance_after=bal_after,
            created_by=reversed_by,
            notes=f"عكس استرداد الرصيد #{locked_tx.pk}: {reason}",
        )
        locked_tx.is_reversed = True
        locked_tx.reversed_by_transaction = reversal
        locked_tx.save(update_fields=["is_reversed", "reversed_by_transaction", "updated_at"])
        journal = JournalEntry.objects.filter(
            school=student.school, source_module="student_fees_credit_refund",
            source_reference=str(locked_tx.pk), is_reversed=False, is_archived=False,
        ).first()
        if journal:
            reverse_journal_entry(
                journal, reason=f"عكس استرداد الرصيد #{locked_tx.pk}: {reason}",
                reversed_by=reversed_by,
            )
        return reversal


def submit_fee_discount_request(
    *, invoice: StudentInvoice, amount: Decimal, reason: str,
    requested_by=None, idempotency_key: str = "",
) -> FeeDiscountRequest:
    """إنشاء طلب خصم وتطبيق الاعتماد التلقائي فقط ضمن سياسة المدرسة."""
    from django.db import transaction
    from apps.students.models import Student
    with transaction.atomic():
        from apps.tenants.models import School
        School.objects.select_for_update().get(pk=invoice.school_id)
        Student.objects.select_for_update().get(
            pk=invoice.student_id, school_id=invoice.school_id,
        )
        locked_invoice = StudentInvoice.objects.select_for_update().get(
            pk=invoice.pk, is_archived=False,
        )
        if locked_invoice.status == StudentInvoice.Status.CANCELLED:
            raise ValidationError("لا يمكن طلب خصم على فاتورة ملغاة.")
        policy, _ = FeeDiscountPolicy.objects.get_or_create(school=locked_invoice.school)
        amount = Decimal(amount)
        if idempotency_key:
            existing = FeeDiscountRequest.objects.filter(
                school=locked_invoice.school, idempotency_key=idempotency_key,
            ).first()
            if existing:
                if (
                    existing.invoice_id != locked_invoice.pk
                    or existing.branch_id != locked_invoice.branch_id
                    or existing.amount != amount
                    or existing.reason != reason.strip()
                ):
                    raise ValidationError("مفتاح منع التكرار مستخدم لطلب خصم مختلف.")
                return existing
        pending_request = FeeDiscountRequest.objects.select_for_update().filter(
            school=locked_invoice.school,
            invoice=locked_invoice,
            status=FeeDiscountRequest.Status.PENDING,
            is_archived=False,
        ).first()
        if pending_request:
            raise ValidationError("يوجد طلب خصم معلق بالفعل لهذه الفاتورة.")
        if amount <= Decimal("0.00"):
            raise ValidationError("قيمة الخصم يجب أن تكون أكبر من الصفر.")
        discountable_amount = max(
            Decimal("0.00"),
            locked_invoice.total_amount - locked_invoice.discount_amount,
        )
        if amount > discountable_amount:
            raise ValidationError("قيمة الخصم تتجاوز إجمالي الفاتورة بعد الخصومات السابقة.")
        new_discount = locked_invoice.discount_amount + amount
        maximum_discount = locked_invoice.total_amount * policy.max_discount_percent / Decimal("100.00")
        if new_discount > maximum_discount:
            raise ValidationError("قيمة الخصم تتجاوز الحد المعتمد في سياسة المدرسة.")
        if new_discount >= locked_invoice.total_amount and not policy.allow_full_exemption:
            raise ValidationError("الإعفاء الكامل غير مسموح وفق سياسة المدرسة.")
        discount = FeeDiscountRequest.objects.create(
            school=locked_invoice.school, branch=locked_invoice.branch,
            invoice=locked_invoice, amount=amount,
            idempotency_key=idempotency_key,
            reason=reason.strip(), requested_by=requested_by,
        )
        if amount <= policy.auto_approval_limit:
            approve_fee_discount_request(
                discount, approved_by=requested_by,
                decision_notes="اعتماد تلقائي وفق سياسة المدرسة",
            )
            discount.refresh_from_db()
        return discount


def approve_fee_discount_request(
    discount_request: FeeDiscountRequest, *, approved_by=None, decision_notes: str = "",
) -> FeeDiscountRequest:
    from django.db import transaction
    from apps.tenants.models import School
    from apps.students.models import Student
    from apps.accounting.services.auto_posting import post_student_invoice_discount_to_journal
    with transaction.atomic():
        School.objects.select_for_update().get(pk=discount_request.school_id)
        request_obj = FeeDiscountRequest.objects.select_for_update().get(pk=discount_request.pk)
        if request_obj.status != FeeDiscountRequest.Status.PENDING:
            raise ValidationError("طلب الخصم اتخذ قراراً مسبقاً.")
        student_id = StudentInvoice.objects.filter(
            pk=request_obj.invoice_id, school_id=request_obj.school_id,
        ).values_list("student_id", flat=True).get()
        student = Student.objects.select_for_update().get(
            pk=student_id, school_id=request_obj.school_id,
        )
        invoice = StudentInvoice.objects.select_for_update().get(
            pk=request_obj.invoice_id, is_archived=False,
        )
        if invoice.status == StudentInvoice.Status.CANCELLED:
            raise ValidationError("لا يمكن اعتماد خصم على فاتورة ملغاة.")
        policy, _ = FeeDiscountPolicy.objects.get_or_create(school=request_obj.school)
        discountable_amount = max(
            Decimal("0.00"), invoice.total_amount - invoice.discount_amount,
        )
        if request_obj.amount > discountable_amount:
            raise ValidationError("قيمة الخصم تتجاوز إجمالي الفاتورة بعد الخصومات السابقة.")
        old_net_amount = max(
            Decimal("0.00"), invoice.total_amount - invoice.discount_amount,
        )
        old_overpayment = max(
            Decimal("0.00"), invoice.paid_amount - old_net_amount,
        )
        new_discount = invoice.discount_amount + request_obj.amount
        max_discount = invoice.total_amount * policy.max_discount_percent / Decimal("100.00")
        if new_discount > max_discount:
            raise ValidationError("الخصم يتجاوز الحد الحالي لسياسة المدرسة.")
        if new_discount >= invoice.total_amount and not policy.allow_full_exemption:
            raise ValidationError("الإعفاء الكامل غير مسموح وفق سياسة المدرسة.")
        invoice.discount_amount = new_discount
        net_amount = max(Decimal("0.00"), invoice.total_amount - invoice.discount_amount)
        if invoice.paid_amount >= net_amount:
            invoice.status = StudentInvoice.Status.PAID
        else:
            invoice.status = (
                StudentInvoice.Status.PARTIAL
                if invoice.paid_amount > Decimal("0.00")
                else StudentInvoice.Status.UNPAID
            )
        invoice.save(update_fields=["discount_amount", "status", "updated_at"])

        new_overpayment = max(
            Decimal("0.00"), invoice.paid_amount - net_amount,
        )
        credit_delta = max(
            Decimal("0.00"), new_overpayment - old_overpayment,
        )
        if credit_delta > Decimal("0.00"):
            balance_before = student.credit_balance
            balance_after = balance_before + credit_delta
            student.credit_balance = balance_after
            _save_student_credit_balance(student)
            StudentCreditTransaction.objects.create(
                school=invoice.school,
                branch=invoice.branch,
                student=student,
                transaction_type=StudentCreditTransaction.TransactionType.ADJUSTMENT,
                amount=credit_delta,
                balance_before=balance_before,
                balance_after=balance_after,
                invoice=invoice,
                created_by=approved_by,
                notes=(
                    f"رصيد دائن ناتج عن خصم معتمد للفاتورة "
                    f"#{invoice.invoice_number} (طلب #{request_obj.pk})"
                ),
            )
        request_obj.status = FeeDiscountRequest.Status.APPROVED
        request_obj.approved_by = approved_by
        request_obj.decided_at = timezone.now()
        request_obj.decision_notes = decision_notes[:2000]
        request_obj.save(update_fields=[
            "status", "approved_by", "decided_at", "decision_notes", "updated_at",
        ])
        post_student_invoice_discount_to_journal(request_obj)
        return request_obj


def reject_fee_discount_request(
    discount_request: FeeDiscountRequest, *, rejected_by=None, reason: str = "",
) -> FeeDiscountRequest:
    from django.db import transaction
    with transaction.atomic():
        request_obj = FeeDiscountRequest.objects.select_for_update().get(pk=discount_request.pk)
        if request_obj.status != FeeDiscountRequest.Status.PENDING:
            raise ValidationError("طلب الخصم اتخذ قراراً مسبقاً.")
        request_obj.status = FeeDiscountRequest.Status.REJECTED
        request_obj.approved_by = rejected_by
        request_obj.decided_at = timezone.now()
        request_obj.decision_notes = reason[:2000]
        request_obj.save(update_fields=[
            "status", "approved_by", "decided_at", "decision_notes", "updated_at",
        ])
        return request_obj
