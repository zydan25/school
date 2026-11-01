"""Payroll, salary contracts, employee advances, and payslips domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class EmployeeContract(TenantOwnedModel):
    """عقود العمل والهياكل الراتبية للمعلمين وموظفي المدرسة."""
    class ContractType(models.TextChoices):
        FULL_TIME = "full_time", "دوام كامل (سنوي)"
        PART_TIME = "part_time", "دوام جزئي / بالحصة"
        TEMPORARY = "temporary", "عقد مؤقت / فصلي"
        PROBATION = "probation", "فترة تجربة"

    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم التدريسي",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    staff_member = models.ForeignKey(
        "staff.StaffMember",
        verbose_name="الموظف الإداري / المشرف",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField("رقم العقد الوظيفي", max_length=50, db_index=True)
    contract_type = models.CharField("نوع العقد", max_length=20, choices=ContractType.choices, default=ContractType.FULL_TIME)
    start_date = models.DateField("تاريخ بدء العقد")
    end_date = models.DateField("تاريخ نهاية العقد (إن وجد)", null=True, blank=True)
    
    # Financial components
    basic_salary = models.DecimalField("الراتب الأساسي", max_digits=12, decimal_places=2)
    housing_allowance = models.DecimalField("بدل السكن", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    transport_allowance = models.DecimalField("بدل المواصلات", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_allowances = models.DecimalField("بدلات ومزايا أخرى", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    insurance_deduction = models.DecimalField("استقطاع التأمينات الاجتماعية", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    
    bank_name = models.CharField("اسم البنك المحول إليه", max_length=100, blank=True)
    iban = models.CharField("رقم الآيبان البنكي (IBAN)", max_length=50, blank=True)
    is_active = models.BooleanField("عقد نشط وسارٍ", default=True)

    class Meta:
        verbose_name = "عقد موظف"
        verbose_name_plural = "عقود الموظفين والرواتب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "contract_number"],
                condition=models.Q(is_archived=False),
                name="payroll_contract_num_uniq",
            )
        ]

    def __str__(self) -> str:
        emp = self.staff_member or self.teacher or "موظف"
        return f"{self.contract_number} - {emp}: {self.gross_salary}"

    def clean(self):
        super().clean()
        if bool(self.teacher_id) == bool(self.staff_member_id):
            raise ValidationError("يجب ربط العقد إما بمعلم أو بموظف إداري واحد فقط (وليس كليهما ولا كلاهما فارغ).")
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم لا ينتمي إلى نفس المدرسة."})
        if self.staff_member_id and self.staff_member.school_id != self.school_id:
            raise ValidationError({"staff_member": "الموظف الإداري لا ينتمي إلى نفس المدرسة."})
        if self.teacher_id and not self.teacher.is_active_teaching:
            raise ValidationError({"teacher": "لا يمكن إنشاء عقد لمعلم غير نشط تدريسياً."})
        if self.staff_member_id and not self.staff_member.is_active:
            raise ValidationError({"staff_member": "لا يمكن إنشاء عقد لموظف غير نشط."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "تاريخ نهاية العقد لا يمكن أن يسبق تاريخ بدايته."})
        salary_fields = (
            "basic_salary", "housing_allowance", "transport_allowance",
            "other_allowances", "insurance_deduction",
        )
        for field in salary_fields:
            value = getattr(self, field)
            if value is not None and value < Decimal("0.00"):
                raise ValidationError({field: "لا يمكن أن تكون مكونات الراتب سالبة."})
        if self.is_active and self.start_date:
            overlapping = EmployeeContract.objects.filter(
                school_id=self.school_id,
                is_active=True,
                is_archived=False,
                start_date__lte=self.end_date or timezone.localdate().replace(year=9999),
            ).exclude(pk=self.pk)
            if self.teacher_id:
                overlapping = overlapping.filter(teacher_id=self.teacher_id, staff_member__isnull=True)
            else:
                overlapping = overlapping.filter(staff_member_id=self.staff_member_id, teacher__isnull=True)
            if self.end_date:
                overlapping = overlapping.filter(
                    models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.start_date)
                )
            else:
                overlapping = overlapping.filter(
                    models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.start_date)
                )
            if overlapping.exists():
                raise ValidationError("يوجد عقد نشط متداخل زمنياً لهذا الموظف؛ أنهِ العقد السابق قبل إضافة عقد جديد.")
        employee_branch_id = (
            self.teacher.branch_id if self.teacher_id else
            self.staff_member.branch_id if self.staff_member_id else None
        )
        if self.branch_id and employee_branch_id and self.branch_id != employee_branch_id:
            raise ValidationError({"branch": "فرع العقد يجب أن يطابق فرع ملف الموظف."})

    @property
    def total_allowances(self) -> Decimal:
        return self.housing_allowance + self.transport_allowance + self.other_allowances

    @property
    def gross_salary(self) -> Decimal:
        return self.basic_salary + self.total_allowances

    @property
    def net_salary(self) -> Decimal:
        return max(Decimal("0.00"), self.gross_salary - self.insurance_deduction)


class EmployeeLoanAdvance(TenantOwnedModel):
    """سلف وقروض الموظفين وأقساط السداد الشهرية."""
    class Status(models.TextChoices):
        PENDING = "pending", "طلب قيد المراجعة"
        APPROVED = "approved", "معتمدة بانتظار الصرف"
        ACTIVE = "active", "مصروفة وقيد الاستقطاع"
        FULLY_REPAID = "fully_repaid", "مسددة بالكامل"
        WRITTEN_OFF = "written_off", "معفاة / مشطوبة"

    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المستفيد من السلفة",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    staff_member = models.ForeignKey(
        "staff.StaffMember",
        verbose_name="الموظف الإداري المستفيد",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    loan_number = models.CharField("رقم السلفة", max_length=50, db_index=True)
    amount = models.DecimalField("مبلغ السلفة الإجمالي", max_digits=12, decimal_places=2)
    monthly_installment = models.DecimalField("القسط الشهري للاستقطاع", max_digits=12, decimal_places=2)
    repaid_amount = models.DecimalField("المبلغ المسدد حتى الآن", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    start_date = models.DateField("تاريخ بدء الاستقطاع")
    status = models.CharField("حالة السلفة", max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField("سبب السلفة وملاحظاتها", blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_employee_loans",
        verbose_name="مقدم طلب السلفة",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_employee_loans",
        verbose_name="معتمد السلفة",
    )
    approved_at = models.DateTimeField("تاريخ اعتماد السلفة", null=True, blank=True)
    disbursed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="disbursed_employee_loans",
        verbose_name="مسؤول صرف السلفة",
    )
    disbursed_at = models.DateTimeField("تاريخ صرف السلفة", null=True, blank=True)
    disbursement_voucher = models.ForeignKey(
        "accounting.PaymentVoucher",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="employee_loans",
        verbose_name="سند صرف السلفة",
    )

    class Meta:
        verbose_name = "سلفة موظف"
        verbose_name_plural = "سلف وقروض الموظفين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "loan_number"],
                condition=models.Q(is_archived=False),
                name="payroll_loan_num_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payroll_loan_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(monthly_installment__gt=0),
                name="payroll_loan_installment_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(repaid_amount__gte=0) & models.Q(repaid_amount__lte=models.F("amount")),
                name="payroll_loan_repaid_range",
            ),
        ]

    def __str__(self) -> str:
        beneficiary = self.teacher or self.staff_member or "موظف"
        return f"سلفة #{self.loan_number} - {beneficiary}: {self.amount} (المتبقي: {self.remaining_amount})"

    def clean(self):
        super().clean()
        if bool(self.teacher_id) == bool(self.staff_member_id):
            raise ValidationError("يجب ربط السلفة إما بمعلم أو بموظف إداري واحد فقط.")
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم لا ينتمي إلى نفس المدرسة."})
        if self.staff_member_id and self.staff_member.school_id != self.school_id:
            raise ValidationError({"staff_member": "الموظف الإداري لا ينتمي إلى نفس المدرسة."})
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "مبلغ السلفة الإجمالي يجب أن يكون أكبر من الصفر."})
        if self.monthly_installment <= Decimal("0.00"):
            raise ValidationError({"monthly_installment": "القسط الشهري للاستقطاع يجب أن يكون أكبر من الصفر."})
        if self.repaid_amount < Decimal("0.00") or self.repaid_amount > self.amount:
            raise ValidationError({"repaid_amount": "إجمالي المسدد يجب أن يكون بين صفر ومبلغ السلفة."})
        if self.disbursement_voucher_id and self.disbursement_voucher.school_id != self.school_id:
            raise ValidationError({"disbursement_voucher": "سند صرف السلفة يجب أن يتبع المدرسة نفسها."})

    @property
    def remaining_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.amount - self.repaid_amount)


class PayrollRun(TenantOwnedModel):
    """مسير الرواتب الشهري المجمع للمدرسة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة (قيد التجهيز)"
        APPROVED = "approved", "معتمد من الإدارة"
        POSTED = "posted", "مرحل محاسبياً (استحقاق مسير)"
        PAID = "paid", "مصروف ومرحل مالياً"

    name = models.CharField("اسم المسير (مثل: مسير رواتب أكتوبر 2026)", max_length=150)
    year = models.PositiveSmallIntegerField("السنة")
    month = models.PositiveSmallIntegerField("الشهر (1-12)")
    
    total_basic = models.DecimalField("إجمالي الأساسي", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_allowances = models.DecimalField("إجمالي البدلات", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_deductions = models.DecimalField("إجمالي الاستقطاعات", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_net = models.DecimalField("صافي الرواتب المستحقة للتحويل", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    
    status = models.CharField("حالة المسير", max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_payrolls",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        verbose_name="القيد المحاسبي المولد للمسير",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payroll_runs",
    )

    class Meta:
        verbose_name = "مسير رواتب شهري"
        verbose_name_plural = "مسيرات الرواتب الشهرية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "year", "month"],
                condition=models.Q(is_archived=False),
                name="payroll_school_year_month_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()}) - {self.total_net}"


class Payslip(TenantOwnedModel):
    """قسيمة الراتب التفصيلية للموظف للشهر المحدد."""
    payroll_run = models.ForeignKey(
        PayrollRun,
        verbose_name="مسير الرواتب التابع له",
        on_delete=models.CASCADE,
        related_name="payslips",
    )
    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم التدريسي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payslips",
    )
    staff_member = models.ForeignKey(
        "staff.StaffMember",
        verbose_name="الموظف الإداري",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payslips",
    )
    basic_salary = models.DecimalField("الراتب الأساسي", max_digits=12, decimal_places=2)
    housing_allowance = models.DecimalField("بدل السكن", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    transport_allowance = models.DecimalField("بدل المواصلات", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_allowances = models.DecimalField("بدلات أخرى", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    overtime_amount = models.DecimalField("مكافآت وحصص إضافية", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    
    # Deductions
    loan_deduction = models.DecimalField("استقطاع سلفة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    absence_deduction = models.DecimalField("خصم غياب وتأخر", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    insurance_deduction = models.DecimalField("استقطاع تأمينات", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    
    net_salary = models.DecimalField("الصافي المستحق", max_digits=12, decimal_places=2)
    payment_date = models.DateField("تاريخ الصرف الفعلي", null=True, blank=True)
    is_paid = models.BooleanField("تم التحويل والصرف", default=False)

    class Meta:
        verbose_name = "قسيمة راتب"
        verbose_name_plural = "قسائم رواتب الموظفين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "payroll_run", "teacher"],
                condition=models.Q(is_archived=False, teacher__isnull=False),
                name="payroll_payslip_teacher_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "payroll_run", "staff_member"],
                condition=models.Q(is_archived=False, staff_member__isnull=False),
                name="payroll_payslip_staff_uniq",
            ),
        ]

    def __str__(self) -> str:
        emp = self.staff_member or self.teacher or "موظف"
        return f"{emp}: {self.net_salary} ({self.payroll_run.name})"

    @property
    def total_earnings(self) -> Decimal:
        return self.basic_salary + self.housing_allowance + self.transport_allowance + self.other_allowances + self.overtime_amount

    @property
    def total_deductions(self) -> Decimal:
        return self.loan_deduction + self.absence_deduction + self.insurance_deduction


class EmployeeLoanRepayment(TenantOwnedModel):
    """سجل أقساط واقتطاعات السلف الشهرية من الرواتب."""
    loan = models.ForeignKey(
        EmployeeLoanAdvance,
        verbose_name="السلفة",
        on_delete=models.CASCADE,
        related_name="repayments",
    )
    payslip = models.ForeignKey(
        Payslip,
        verbose_name="قسيمة الراتب",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="loan_repayments",
    )
    payroll_run = models.ForeignKey(
        PayrollRun,
        verbose_name="مسير الرواتب",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="loan_repayments",
    )
    amount = models.DecimalField("مبلغ الخصم المسدد", max_digits=12, decimal_places=2)
    balance_before = models.DecimalField("رصيد السلفة قبل السداد", max_digits=12, decimal_places=2)
    balance_after = models.DecimalField("رصيد السلفة بعد السداد", max_digits=12, decimal_places=2)
    repaid_at = models.DateField("تاريخ الاستقطاع", default=timezone.localdate)
    is_reversed = models.BooleanField("تم عكس القسط", default=False)
    idempotency_key = models.CharField("مفتاح منع تكرار السداد", max_length=100, blank=True, default="")
    receipt_voucher = models.ForeignKey(
        "accounting.ReceiptVoucher",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="employee_loan_repayments",
        verbose_name="سند تحصيل السداد اليدوي",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_employee_loan_repayments",
        verbose_name="مسجل عملية السداد",
    )
    notes = models.CharField("ملاحظات السداد", max_length=500, blank=True)

    class Meta:
        verbose_name = "سجل سداد سلفة"
        verbose_name_plural = "سجلات سداد سلف الموظفين"
        ordering = ["-repaid_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False, idempotency_key__gt=""),
                name="payroll_loan_repay_idem_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payroll_loan_repayment_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(balance_before__gte=0) & models.Q(balance_after__gte=0),
                name="payroll_loan_repayment_balances_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.loan.loan_number}: {self.amount} (المتبقي: {self.balance_after})"
