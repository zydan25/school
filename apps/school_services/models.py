"""School support services models: transportation, library, and textbook distribution.

Legacy clinic models remain in the schema for historical data compatibility only;
they are deliberately not exposed through API or school administration.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel

# -----------------------------------------------------------------------------
# 1. School Transportation (النقل المدرسي والحافلات)
# -----------------------------------------------------------------------------

class BusRoute(TenantOwnedModel):
    """خطوط سير الحافلات المدرسية وسائقيها ومشرفيها والتعاقد المالي."""
    route_name = models.CharField("اسم خط السير", max_length=150)
    route_code = models.CharField("رمز الخط", max_length=50, db_index=True)
    destination_area = models.CharField("الوجهة / المنطقة المغطاة", max_length=200, blank=True)
    bus_number = models.CharField("رقم الحافلة / اللوحة", max_length=50)
    bus_capacity = models.PositiveSmallIntegerField("سعة الحافلة (مقاعد)", default=30)
    driver_name = models.CharField("اسم السائق", max_length=120)
    driver_phone = models.CharField("هاتف السائق", max_length=30)
    driver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب تسجيل الدخول للسائق (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="driven_buses",
    )
    supervisor_teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المشرف على الحافلة",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supervised_buses",
    )
    supervisor_name = models.CharField("اسم مشرف/ة الحافلة (نصي)", max_length=120, blank=True)
    supervisor_phone = models.CharField("هاتف المشرف/ة", max_length=30, blank=True)
    morning_pickup_time = models.TimeField("وقت بداية الانطلاق الصباحي", null=True, blank=True)
    afternoon_dropoff_time = models.TimeField("وقت بداية رحلة العودة", null=True, blank=True)
    monthly_fee = models.DecimalField("رسوم اشتراك الطالب الشهري", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    # Financial Contract with Bus / Driver
    class CompensationType(models.TextChoices):
        MONTHLY_FLAT = "monthly_flat", "مبلغ شهري مقطوع ثابت"
        PER_STUDENT = "per_student", "عمولة / أجر شهري بحسب عدد الطلاب الركاب"

    class ContractorType(models.TextChoices):
        EMPLOYEE = "employee", "موظف في كادر المدرسة (راتب وسحوبات)"
        EXTERNAL = "external", "متعهد / سائق خارجي (ذمم موردين)"

    compensation_type = models.CharField(
        "طريقة احتساب مستحقات الباص",
        max_length=20,
        choices=CompensationType.choices,
        default=CompensationType.MONTHLY_FLAT,
    )
    contract_amount = models.DecimalField(
        "قيمة التعاقد (المبلغ المقطوع أو نصيب الراكب)",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    contractor_type = models.CharField(
        "صفة تعاقد السائق/الحافلة",
        max_length=20,
        choices=ContractorType.choices,
        default=ContractorType.EMPLOYEE,
    )
    is_active = models.BooleanField("خط نشط وسارٍ", default=True)

    class Meta:
        verbose_name = "خط سير حافلة"
        verbose_name_plural = "خطوط النقل المدرسي"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "route_code"],
                condition=models.Q(is_archived=False),
                name="services_bus_route_code_uniq",
            )
        ]
        permissions = [
            ("bill_studentbussubscription", "يمكنه إصدار فواتير اشتراكات النقل"),
        ]

    def clean(self):
        super().clean()
        if self.bus_capacity < 1:
            raise ValidationError({"bus_capacity": "سعة الحافلة يجب أن تكون مقعداً واحداً على الأقل."})
        if self.monthly_fee < Decimal("0.00") or self.contract_amount < Decimal("0.00"):
            raise ValidationError("رسوم النقل وقيمة التعاقد لا يمكن أن تكونا سالبتين.")
        if self.pk:
            active_count = self.student_subscriptions.filter(
                status=StudentBusSubscription.Status.ACTIVE,
                is_archived=False,
            ).count()
            if self.bus_capacity < active_count:
                raise ValidationError({"bus_capacity": "لا يمكن خفض سعة الحافلة عن عدد اشتراكاتها النشطة."})
            if (not self.is_active or self.is_archived) and active_count:
                raise ValidationError({"is_active": "أوقف أو ألغِ اشتراكات الطلاب قبل إيقاف خط النقل أو أرشفته."})

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if not self._state.adding:
                type(self).objects.select_for_update().get(pk=self.pk)
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("خطوط النقل تحفظ كسجل تشغيلي ولا تحذف نهائياً.")

    def __str__(self) -> str:
        return f"{self.route_name} [{self.route_code}] - حافلة ({self.bus_number})"


class StudentBusSubscription(TenantOwnedModel):
    """اشتراكات الطلاب في خدمة النقل المدرسي."""
    class SubscriptionType(models.TextChoices):
        TWO_WAY = "two_way", "ذهاب وعودة (كامل)"
        MORNING_ONLY = "morning_only", "صباحي فقط (ذهاب)"
        AFTERNOON_ONLY = "afternoon_only", "مسائي فقط (عودة)"

    class Status(models.TextChoices):
        ACTIVE = "active", "سارٍ ونشط"
        SUSPENDED = "suspended", "موقوف مؤقتاً"
        CANCELLED = "cancelled", "ملغى"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المشترك",
        on_delete=models.CASCADE,
        related_name="bus_subscriptions",
    )
    bus_route = models.ForeignKey(
        BusRoute,
        verbose_name="خط السير",
        on_delete=models.PROTECT,
        related_name="student_subscriptions",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="bus_subscriptions",
    )
    subscription_type = models.CharField(
        "نوع الاشتراك",
        max_length=20,
        choices=SubscriptionType.choices,
        default=SubscriptionType.TWO_WAY,
    )
    pickup_address = models.TextField("عنوان نقطة الالتقاط والمنزل بالتفصيل", blank=True)
    status = models.CharField("حالة الاشتراك", max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = "اشتراك نقل طالب"
        verbose_name_plural = "اشتراكات النقل المدرسي للطلاب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "academic_year"],
                condition=models.Q(is_archived=False),
                name="services_student_bus_sub_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student}: {self.bus_route.route_name} ({self.get_subscription_type_display()})"

    def clean(self):
        super().clean()
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "العام الدراسي لا ينتمي إلى هذه المدرسة."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا ينتمي إلى هذه المدرسة."})
        if self.bus_route_id and self.bus_route.school_id != self.school_id:
            raise ValidationError({"bus_route": "خط النقل لا ينتمي إلى هذه المدرسة."})
        if self.status == self.Status.ACTIVE and self.bus_route_id and not self.bus_route.is_active:
            raise ValidationError({"bus_route": "لا يمكن تفعيل اشتراك على خط نقل متوقف."})

    def save(self, *args, **kwargs):
        # Serialize capacity checks on the route row so concurrent subscriptions
        # cannot exceed the configured number of seats.
        from django.db import transaction

        with transaction.atomic():
            BusRoute.objects.select_for_update().get(
                pk=self.bus_route_id, school_id=self.school_id, is_archived=False
            )
            super().save(*args, **kwargs)
            if self.status == self.Status.ACTIVE:
                route = BusRoute.objects.get(pk=self.bus_route_id, school_id=self.school_id)
                active_count = route.student_subscriptions.filter(
                    status=self.Status.ACTIVE, is_archived=False
                ).count()
                if active_count > route.bus_capacity:
                    raise ValidationError({"bus_route": "اكتملت سعة الحافلة لهذا الخط."})

    def archive(self, *, actor=None, reason: str = "") -> None:
        if self.status == self.Status.ACTIVE:
            raise ValidationError("لا تؤرشف اشتراك نقل نشطاً؛ أوقفه أو ألغِه أولاً.")
        return super().archive(actor=actor, reason=reason)

    def delete(self, *args, **kwargs):
        raise ValidationError("اشتراكات النقل تحفظ كسجل تاريخي ولا تحذف نهائياً.")


class BusSubscriptionCharge(TenantOwnedModel):
    """One immutable monthly invoice link per active transportation subscription."""
    subscription = models.ForeignKey(
        StudentBusSubscription, verbose_name="اشتراك النقل", on_delete=models.PROTECT,
        related_name="monthly_charges",
    )
    invoice = models.OneToOneField(
        "student_fees.StudentInvoice", verbose_name="فاتورة الطالب", on_delete=models.PROTECT,
        related_name="bus_subscription_charge",
    )
    billing_year = models.PositiveSmallIntegerField("سنة الفوترة")
    billing_month = models.PositiveSmallIntegerField("شهر الفوترة")
    amount = models.DecimalField("قيمة الفاتورة وقت الإصدار", max_digits=12, decimal_places=2)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="أصدرها", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="issued_bus_subscription_charges",
    )

    class Meta:
        verbose_name = "فاتورة اشتراك نقل"
        verbose_name_plural = "فواتير اشتراكات النقل"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "subscription", "billing_year", "billing_month"],
                condition=models.Q(is_archived=False),
                name="school_services_bus_charge_period_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(billing_month__gte=1) & models.Q(billing_month__lte=12),
                name="school_services_bus_charge_month_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if not 1900 <= self.billing_year <= 9999:
            raise ValidationError({"billing_year": "سنة الفوترة يجب أن تكون بين 1900 و9999."})
        if not 1 <= self.billing_month <= 12:
            raise ValidationError({"billing_month": "شهر الفوترة يجب أن يكون بين 1 و12."})
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "قيمة فاتورة النقل يجب أن تكون أكبر من صفر."})
        if self.subscription_id and self.subscription.school_id != self.school_id:
            raise ValidationError({"subscription": "اشتراك النقل لا يتبع المدرسة نفسها."})
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "فاتورة النقل لا تتبع المدرسة نفسها."})
        if self.subscription_id and self.invoice_id:
            if self.invoice.student_id != self.subscription.student_id:
                raise ValidationError({"invoice": "فاتورة النقل لا تخص الطالب صاحب الاشتراك."})
            if self.invoice.total_amount != self.amount:
                raise ValidationError({"amount": "قيمة قيد اشتراك النقل يجب أن تطابق قيمة فاتورته."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(
                "school_id", "subscription_id", "invoice_id", "billing_year",
                "billing_month", "amount", "issued_by_id",
            ).first()
            if previous and any(
                previous[field] != getattr(self, field)
                for field in (
                    "school_id", "subscription_id", "invoice_id", "billing_year",
                    "billing_month", "amount", "issued_by_id",
                )
            ):
                raise ValidationError("سجل فاتورة النقل تاريخي ولا يجوز تغيير بياناته المالية.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا تحذف فواتير اشتراكات النقل؛ صححها بقيد عكسي موثق.")


# -----------------------------------------------------------------------------
# 2. School Library (المكتبة المدرسية واستعارة الكتب)
# -----------------------------------------------------------------------------

class LibraryBook(TenantOwnedModel):
    """دليل الكتب والمراجع في المكتبة المدرسية."""
    isbn = models.CharField("الرقم المعياري الدولي (ISBN / الرمز)", max_length=50, blank=True, db_index=True)
    title = models.CharField("عنوان الكتاب / المرجع", max_length=250)
    author = models.CharField("المؤلف", max_length=150, blank=True)
    publisher = models.CharField("دار النشر", max_length=150, blank=True)
    category = models.CharField("التصنيف أو الفن (علمي، أدبي، إسلامي، روايات)", max_length=100, blank=True)
    publication_year = models.PositiveSmallIntegerField("سنة النشر", null=True, blank=True)
    total_copies = models.PositiveSmallIntegerField("إجمالي النسخ المتوفرة", default=1)
    available_copies = models.PositiveSmallIntegerField("النسخ المتاحة حالياً للإعارة", default=1)
    shelf_location = models.CharField("موقع الرف والقاعة", max_length=100, blank=True)

    class Meta:
        verbose_name = "كتاب مدرسي / مرجع"
        verbose_name_plural = "المكتبة المدرسية والكتب"
        permissions = [
            ("manage_library_policy", "يمكنه إدارة سياسة المكتبة والغرامات"),
        ]

    def clean(self):
        super().clean()
        if self.total_copies < 1:
            raise ValidationError({"total_copies": "يجب أن يحتوي سجل الكتاب على نسخة واحدة على الأقل."})
        if self.available_copies < 0 or self.available_copies > self.total_copies:
            raise ValidationError({"available_copies": "عدد النسخ المتاحة غير متسق مع إجمالي النسخ."})

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if not self._state.adding:
                original = type(self).objects.select_for_update().filter(pk=self.pk).first()
                if original:
                    outstanding = original.total_copies - original.available_copies
                    if self.total_copies < outstanding:
                        raise ValidationError({"total_copies": "لا يمكن خفض النسخ عن عدد النسخ المعارة."})
                    if (
                        self.available_copies != original.available_copies
                        and not getattr(self, "_allow_library_stock_update", False)
                    ):
                        raise ValidationError("النسخ المتاحة تُدار من خلال إجراءات الإعارة والإرجاع فقط.")
                    if not getattr(self, "_allow_library_stock_update", False):
                        self.available_copies = self.total_copies - outstanding
            return super().save(*args, **kwargs)

    def archive(self, *, actor=None, reason: str = "") -> None:
        if self.loans.filter(
            status__in=["borrowed", "overdue"],
            is_archived=False,
        ).exists():
            raise ValidationError("لا تؤرشف كتاباً له إعارات لم تتم تسويتها.")
        return super().archive(actor=actor, reason=reason)

    def delete(self, *args, **kwargs):
        raise ValidationError("سجلات الكتب تحفظ للأثر التاريخي؛ استخدم الأرشفة بدلاً من الحذف.")

    def __str__(self) -> str:
        return f"{self.title} - {self.author} (متاح: {self.available_copies}/{self.total_copies})"


class BookLoan(TenantOwnedModel):
    """سجل استعارة الكتب للطلاب أو المعلمين."""
    class Status(models.TextChoices):
        BORROWED = "borrowed", "معار حالياً"
        RETURNED = "returned", "مسترجع بالكامل"
        OVERDUE = "overdue", "متأخر عن موعد الإرجاع"
        LOST = "lost", "مفقود أو تالف"

    book = models.ForeignKey(
        LibraryBook,
        verbose_name="الكتاب المستعار",
        on_delete=models.PROTECT,
        related_name="loans",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المستعير (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_loans",
    )
    teacher = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم المستعير (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_loans",
    )
    borrow_date = models.DateField("تاريخ الاستعارة", default=timezone.localdate)
    due_date = models.DateField("تاريخ الاستحقاق والإرجاع")
    return_date = models.DateField("تاريخ الإرجاع الفعلي", null=True, blank=True)
    status = models.CharField("حالة الإعارة", max_length=20, choices=Status.choices, default=Status.BORROWED)
    fine_amount = models.DecimalField("غرامة التأخير أو التلف (إن وجدت)", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    fine_invoice = models.ForeignKey(
        "student_fees.StudentInvoice", verbose_name="فاتورة غرامة الإعارة",
        null=True, blank=True, on_delete=models.PROTECT, related_name="library_fine_loans",
    )
    renewal_count = models.PositiveSmallIntegerField("عدد مرات التجديد", default=0)
    notes = models.TextField("ملاحظات أمين المكتبة", blank=True)

    class Meta:
        verbose_name = "سجل إعارة كتاب"
        verbose_name_plural = "إعارات المكتبة المدرسية"
        permissions = [
            ("return_bookloan", "يمكنه إرجاع كتاب مستعار"),
            ("renew_bookloan", "يمكنه تجديد إعارة كتاب"),
            ("marklost_bookloan", "يمكنه تسجيل كتاب مستعار كمفقود"),
        ]

    def __str__(self) -> str:
        borrower = self.student or self.teacher or "مستعير غير محدد"
        return f"{self.book.title} -> {borrower} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if bool(self.student_id) == bool(self.teacher_id):
            raise ValidationError("يجب تحديد مستعير واحد فقط: طالب أو معلم.")
        if self.book_id and self.book.school_id != self.school_id:
            raise ValidationError({"book": "الكتاب لا يتبع المدرسة نفسها."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة نفسها."})
        if self.teacher_id and self.teacher.school_id != self.school_id:
            raise ValidationError({"teacher": "المعلم لا يتبع المدرسة نفسها."})
        if self.borrow_date and self.due_date and self.due_date < self.borrow_date:
            raise ValidationError({"due_date": "موعد الإرجاع لا يمكن أن يسبق تاريخ الاستعارة."})
        if self.fine_amount < Decimal("0.00"):
            raise ValidationError({"fine_amount": "الغرامة لا يمكن أن تكون سالبة."})
        if self.fine_invoice_id and self.fine_invoice.school_id != self.school_id:
            raise ValidationError({"fine_invoice": "فاتورة الغرامة لا تتبع المدرسة نفسها."})
        if self.status == self.Status.RETURNED and not self.return_date:
            raise ValidationError({"return_date": "تاريخ الإرجاع مطلوب عند إغلاق الإعارة."})
        if self._state.adding and self.status == self.Status.BORROWED:
            if self.book.available_copies <= 0:
                raise ValidationError({"book": "لا توجد نسخ متاحة حالياً من هذا الكتاب للإعارة."})

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            is_new = self._state.adding
            previous = None
            if not is_new:
                previous = type(self).objects.select_for_update().filter(
                    pk=self.pk
                ).values(
                    "status", "book_id", "student_id", "teacher_id", "borrow_date",
                    "due_date", "fine_amount", "fine_invoice_id", "renewal_count",
                ).first()
                if previous:
                    immutable_identity = (
                        "book_id", "student_id", "teacher_id", "borrow_date"
                    )
                    if any(
                        previous[field] != getattr(self, field)
                        for field in immutable_identity
                    ):
                        raise ValidationError(
                            "هوية الإعارة والمستعير لا تتغير بعد تسجيل الإعارة."
                        )
                    protected_lifecycle = (
                        "status", "due_date", "fine_amount",
                        "fine_invoice_id", "renewal_count",
                    )
                    if (
                        any(
                            previous[field] != getattr(self, field)
                            for field in protected_lifecycle
                        )
                        and not getattr(self, "_allow_library_service_update", False)
                    ):
                        raise ValidationError(
                            "حالة الإعارة ومواعيدها وغراماتها لا تعدل مباشرة؛ "
                            "استخدم إجراءات المكتبة المعتمدة."
                        )
            if is_new and self.status != self.Status.BORROWED:
                raise ValidationError(
                    "تبدأ الإعارة بحالة معار حالياً ثم تتغير عبر إجراءات المكتبة."
                )

            super().save(*args, **kwargs)
            if is_new:
                book = LibraryBook.objects.select_for_update().get(pk=self.book_id)
                if book.available_copies <= 0:
                    raise ValidationError({
                        "book": "لا توجد نسخ متاحة حالياً من هذا الكتاب للإعارة."
                    })
                book.available_copies -= 1
                book._allow_library_stock_update = True
                book.save(update_fields=["available_copies"])
            elif previous and (
                previous["status"] != self.Status.RETURNED
                and self.status == self.Status.RETURNED
            ):
                book = LibraryBook.objects.select_for_update().get(pk=self.book_id)
                if book.available_copies < book.total_copies:
                    book.available_copies += 1
                    book._allow_library_stock_update = True
                    book.save(update_fields=["available_copies"])

    def archive(self, *, actor=None, reason: str = "") -> None:
        if self.status in {self.Status.BORROWED, self.Status.OVERDUE}:
            raise ValidationError("لا تؤرشف إعارة نشطة أو متأخرة؛ أرجع الكتاب أو سجل فقده أولاً.")
        return super().archive(actor=actor, reason=reason)

    def delete(self, *args, **kwargs):
        raise ValidationError("سجلات الإعارة تاريخية؛ لا يجوز حذفها من النظام.")


# -----------------------------------------------------------------------------
# 3. Transportation Financial Settlements (المحاسبة المالية للحافلات والسائقين)
# -----------------------------------------------------------------------------

class BusFinancialSettlement(TenantOwnedModel):
    """
    سجل المحاسبة المالية للحافلة والسائق.
    يحاسب السائق/المتعهد إما كموظف أو متعهد، وبحسب عدد الطلاب أو مبلغ مقطوع،
    مع رصد السحوبات والمستحقات والربط بالقيود وسندات الصرف.
    """
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة تسوية"
        APPROVED = "approved", "معتمدة"
        PAID = "paid", "مصروفة بالكامل"

    bus_route = models.ForeignKey(
        BusRoute,
        verbose_name="خط السير / الحافلة",
        on_delete=models.PROTECT,
        related_name="settlements",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="السنة الدراسية",
        on_delete=models.PROTECT,
        related_name="bus_settlements",
    )
    month = models.PositiveSmallIntegerField("الشهر المالي (1-12)")
    year = models.PositiveSmallIntegerField("السنة المالية (مثال: 2026)")
    settlement_date = models.DateField("تاريخ التسوية", default=timezone.localdate)
    student_count = models.PositiveSmallIntegerField("عدد الطلاب الركاب الفعلي", default=0)
    rate_applied = models.DecimalField("معدل الاحتساب المطبق", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    gross_due = models.DecimalField("إجمالي المستحق للسائق/المتعهد", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    advances_withdrawn = models.DecimalField("إجمالي السحوبات والدفعات المقدمة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_payable = models.DecimalField("صافي المبلغ المتبقي المستحق", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة التسوية", max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_bus_settlements",
    )
    payment_voucher = models.ForeignKey(
        "accounting.PaymentVoucher",
        verbose_name="سند الصرف المالي المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bus_settlements",
    )
    notes = models.TextField("ملاحظات وشرح التسوية", blank=True)

    class Meta:
        verbose_name = "تسوية مالية لحافلة"
        verbose_name_plural = "المحاسبة المالية للحافلات والسائقين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "bus_route", "academic_year", "year", "month"],
                condition=models.Q(is_archived=False),
                name="school_services_bus_settlement_uniq",
            )
        ]
        permissions = [
            ("calculate_busfinancialsettlement", "يمكنه احتساب تسوية النقل"),
            ("approve_busfinancialsettlement", "يمكنه اعتماد تسوية النقل وصرفها"),
        ]

    def clean(self):
        super().clean()
        if not 1 <= self.month <= 12:
            raise ValidationError({"month": "يجب أن يكون الشهر بين 1 و12."})
        for name, related in (("bus_route", self.bus_route), ("academic_year", self.academic_year)):
            if related is not None and related.school_id != self.school_id:
                raise ValidationError({name: "السجل المرتبط لا يتبع المدرسة نفسها."})
        if min(self.advances_withdrawn, self.gross_due, self.net_payable, self.rate_applied) < Decimal("0.00"):
            raise ValidationError("قيم التسوية المالية لا يمكن أن تكون سالبة.")

    def __str__(self) -> str:
        return f"تسوية {self.bus_route.bus_number} - شهر {self.month}/{self.year}: صافي {self.net_payable}"

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if not self._state.adding:
                previous = type(self).objects.select_for_update().filter(
                    pk=self.pk
                ).values(
                    "status", "school_id", "bus_route_id", "academic_year_id",
                    "month", "year", "advances_withdrawn", "rate_applied",
                    "student_count", "gross_due", "net_payable", "payment_voucher_id",
                    "approved_by_id",
                ).first()
                if previous:
                    if previous["school_id"] != self.school_id:
                        raise ValidationError("لا تنقل تسوية مالية إلى مدرسة أخرى.")
                    if previous["status"] != self.Status.DRAFT:
                        protected_fields = (
                            "bus_route_id", "academic_year_id", "month", "year",
                            "advances_withdrawn", "rate_applied", "student_count",
                            "gross_due", "net_payable",
                        )
                        if any(
                            previous[field] != getattr(self, field)
                            for field in protected_fields
                        ):
                            raise ValidationError("التسوية المعتمدة تقفل قيمها المالية ولا تعدل.")
                    workflow_fields = ("status", "payment_voucher_id", "approved_by_id")
                    if (
                        any(
                            previous[field] != getattr(self, field)
                            for field in workflow_fields
                        )
                        and not getattr(self, "_allow_bus_settlement_workflow_update", False)
                    ):
                        raise ValidationError("اعتماد التسوية وربط سند الصرف يتمان من إجراء الاعتماد فقط.")
            if self.payment_voucher_id and self.payment_voucher.school_id != self.school_id:
                raise ValidationError({"payment_voucher": "سند الصرف لا يتبع المدرسة نفسها."})
            if self.status == self.Status.PAID and not self.payment_voucher_id:
                raise ValidationError({"payment_voucher": "لا تعد التسوية مصروفة دون سند صرف مرتبط."})
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("التسويات المالية سجل تدقيقي ولا يجوز حذفها.")

    def calculate_due(self):
        """احتساب المستحق آلياً بحسب طريقة التعاقد وعدد الطلاب المسجلين."""
        active_subs = self.bus_route.student_subscriptions.filter(
            status=StudentBusSubscription.Status.ACTIVE,
            academic_year=self.academic_year,
            is_archived=False,
        ).count()
        self.student_count = active_subs
        self.rate_applied = self.bus_route.contract_amount

        if self.bus_route.compensation_type == BusRoute.CompensationType.PER_STUDENT:
            self.gross_due = Decimal(self.student_count) * self.rate_applied
        else:
            self.gross_due = self.rate_applied

        self.net_payable = max(Decimal("0.00"), self.gross_due - self.advances_withdrawn)

    def approve_and_create_payment_voucher(self, approved_by_user=None):
        """اعتماد التسوية وإنشاء سند صرف مرحّل قبل اعتبار المستحق مصروفاً."""
        if self.status == self.Status.PAID and self.payment_voucher_id:
            voucher = self.payment_voucher
            if voucher.status != voucher.Status.POSTED or not voucher.journal_entry_id:
                raise ValidationError("التسوية موسومة كمصروفة لكن سند الصرف غير مرحّل؛ يجب مراجعتها.")
            return voucher

        from django.db import transaction

        from apps.accounting.models import Account, PaymentVoucher
        from apps.accounting.services.auto_posting import post_payment_voucher_to_journal

        with transaction.atomic():
            self.calculate_due()
            if approved_by_user:
                self.approved_by = approved_by_user

            if self.net_payable > Decimal("0.00"):
                expense_acc = Account.objects.filter(
                    school=self.school, code="5205", is_leaf=True
                ).first()
                cash_acc = Account.objects.filter(
                    school=self.school, code="1101", is_leaf=True
                ).first()
                if expense_acc is None or cash_acc is None:
                    raise ValidationError(
                        "حساب مصروفات النقل أو حساب الصندوق غير مهيأ في دليل حسابات المدرسة."
                    )

                voucher_number = (
                    f"PV-BUS-{self.bus_route.bus_number}-{self.year}-{self.month:02d}"
                )
                if self.payment_voucher_id:
                    voucher = PaymentVoucher.objects.select_for_update().get(
                        pk=self.payment_voucher_id, school=self.school
                    )
                else:
                    voucher, _ = PaymentVoucher.objects.get_or_create(
                        school=self.school,
                        voucher_number=voucher_number,
                        defaults={
                            "date": self.settlement_date,
                            "paid_to": (
                                f"السائق: {self.bus_route.driver_name} "
                                f"(حافلة {self.bus_route.bus_number})"
                            ),
                            "amount": self.net_payable,
                            "debit_account": expense_acc,
                            "credit_account": cash_acc,
                            "description": (
                                f"مستحقات نقل مدرسي شهر {self.month}/{self.year} "
                                f"- {self.student_count} طالب"
                            ),
                            "status": PaymentVoucher.Status.DRAFT,
                        },
                    )
                if (
                    voucher.amount != self.net_payable
                    or voucher.debit_account_id != expense_acc.pk
                    or voucher.credit_account_id != cash_acc.pk
                    or voucher.school_id != self.school_id
                ):
                    raise ValidationError(
                        "سند الصرف الموجود لا يطابق قيمة التسوية وحساباتها؛ لا يمكن إعادة استخدامه."
                    )
                if voucher.status == PaymentVoucher.Status.DRAFT and not voucher.journal_entry_id:
                    post_payment_voucher_to_journal(voucher)
                voucher.refresh_from_db()
                if (
                    voucher.status != PaymentVoucher.Status.POSTED
                    or not voucher.journal_entry_id
                ):
                    raise ValidationError(
                        "تعذر ترحيل سند صرف تسوية الحافلة محاسبياً؛ لم تعتمد التسوية."
                    )
                self.payment_voucher = voucher
                self.status = self.Status.PAID
            else:
                self.status = self.Status.APPROVED

            self._allow_bus_settlement_workflow_update = True
            self.save()
            return self.payment_voucher


# -----------------------------------------------------------------------------
# 4. Student Textbooks & Fee Delivery (توزيع الكتب والرسوم الخاصة)
# -----------------------------------------------------------------------------

class StudentBookDistribution(TenantOwnedModel):
    """
    تسليم وتوزيع الكتب المدرسية والرسوم الخاصة بها على الطلاب.
    يتيح متابعة استلام كل طالب للكتب ورسومها وتحديث المخزون والفاتورة المالية.
    """
    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "بانتظار الصرف والتسليم"
        DELIVERED = "delivered", "تم التسليم للطالب"
        RETURNED = "returned", "مسترجع للمستودع"

    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="book_distributions",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="book_distributions",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        verbose_name="الصنف المخزني المرتبط (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_distributions",
    )
    book_title = models.CharField("اسم الكتاب / الحزمة المدرسية", max_length=200)
    quantity = models.DecimalField("الكمية المسلمة", max_digits=6, decimal_places=2, default=Decimal("1.00"))
    fee_amount = models.DecimalField("قيمة رسم الكتاب المقيد على الطالب", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_status = models.CharField("حالة التسليم", max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    delivered_at = models.DateTimeField("تاريخ ووقت التسليم الفعلي", null=True, blank=True)
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="الموظف المسلّم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivered_books",
    )
    returned_at = models.DateTimeField("تاريخ ووقت الاسترجاع", null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="الموظف المستلم للاسترجاع",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="returned_books",
    )
    invoice = models.ForeignKey(
        "student_fees.StudentInvoice",
        verbose_name="الفاتورة المقيد عليها الرسم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_distributions",
    )
    notes = models.TextField("ملاحظات التسليم", blank=True)

    class Meta:
        verbose_name = "تسليم كتب مدرسية"
        verbose_name_plural = "توزيع الكتب المدرسية ورسومها"
        permissions = [
            ("deliver_studentbookdistribution", "يمكنه تسليم الكتب للطلاب"),
            ("return_studentbookdistribution", "يمكنه استرجاع الكتب من الطلاب"),
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع المدرسة نفسها."})
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة نفسها."})
        if self.inventory_item_id and self.inventory_item.school_id != self.school_id:
            raise ValidationError({"inventory_item": "الصنف المخزني لا يتبع المدرسة نفسها."})
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "الفاتورة لا تتبع المدرسة نفسها."})
        if self.quantity <= Decimal("0.00") or self.fee_amount < Decimal("0.00"):
            raise ValidationError("الكمية يجب أن تكون موجبة والرسم لا يمكن أن يكون سالباً.")

    def __str__(self) -> str:
        return f"{self.student.first_name}: {self.book_title} (كمية: {self.quantity}) [{self.get_delivery_status_display()}]"

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if not self._state.adding and self.pk:
                previous = type(self).objects.select_for_update().filter(
                    pk=self.pk
                ).values(
                    "delivery_status", "delivered_at", "delivered_by_id",
                    "returned_at", "returned_by_id", "invoice_id",
                    "student_id", "academic_year_id", "inventory_item_id",
                    "book_title", "quantity", "fee_amount",
                ).first()
                if previous:
                    immutable_after_delivery = (
                        "student_id", "academic_year_id", "inventory_item_id",
                        "book_title", "quantity", "fee_amount",
                    )
                    if (
                        previous["delivery_status"] != self.DeliveryStatus.PENDING
                        and any(
                            previous[field] != getattr(self, field)
                            for field in immutable_after_delivery
                        )
                    ):
                        raise ValidationError("تفاصيل تسليم الكتاب تقفل بعد بدء عملية التسليم.")
                    lifecycle_fields = (
                        "delivery_status", "delivered_at", "delivered_by_id",
                        "returned_at", "returned_by_id", "invoice_id",
                    )
                    if (
                        any(
                            previous[field] != getattr(self, field)
                            for field in lifecycle_fields
                        )
                        and not getattr(self, "_allow_distribution_service_update", False)
                    ):
                        raise ValidationError(
                            "حالة التسليم والفاتورة وسجل الاسترجاع لا تعدل مباشرة؛ "
                            "استخدم إجراءات تسليم الكتب."
                        )
            return super().save(*args, **kwargs)

    def archive(self, *, actor=None, reason: str = "") -> None:
        if self.delivery_status == self.DeliveryStatus.DELIVERED:
            raise ValidationError("لا تؤرشف تسليماً لم تتم تسويته؛ استرجع الكتاب أولاً.")
        return super().archive(actor=actor, reason=reason)

    def delete(self, *args, **kwargs):
        raise ValidationError("سجلات تسليم الكتب تاريخية؛ لا يجوز حذفها من النظام.")

    def deliver_book(self, user=None):
        """تسليم الكتاب للطالب وخصم الكمية من المخزون وتوثيق العملية مع قفل تشاؤمي."""
        from django.db import transaction
        with transaction.atomic():
            locked_dist = StudentBookDistribution.objects.select_for_update().get(pk=self.pk)
            if locked_dist.delivery_status == self.DeliveryStatus.DELIVERED:
                return
            if locked_dist.inventory_item:
                from apps.inventory.services import record_stock_movement
                item = locked_dist.inventory_item
                record_stock_movement(
                    school=locked_dist.school,
                    item=item,
                    warehouse=item.warehouse,
                    movement_type="issue",
                    quantity=locked_dist.quantity,
                    unit_cost=item.unit_cost,
                    idempotency_key=f"book-delivery-{locked_dist.pk}",
                    notes=f"تسليم كتاب للطالب {locked_dist.student.student_id_number}",
                    recipient_name=f"الطالب: {locked_dist.student}",
                    reference=f"تسليم كتاب للطالب {locked_dist.student.student_id_number}",
                    created_by=user,
                )
            # الربط المالي التلقائي: إنشاء فاتورة رسوم الكتاب إن وجدت قيمة للرسم
            if locked_dist.fee_amount > Decimal("0.00") and not locked_dist.invoice:
                from apps.student_fees.models import FeeCategory, StudentInvoice, StudentInvoiceItem
                from apps.accounting.services.auto_posting import post_student_invoice_to_journal
                import uuid
                cat, _ = FeeCategory.objects.get_or_create(
                    school=locked_dist.school,
                    code="BOOKS",
                    defaults={"name": "رسوم الكتب والمستلزمات الدراسية", "is_mandatory": False},
                )
                inv = StudentInvoice.objects.create(
                    school=locked_dist.school,
                    student=locked_dist.student,
                    academic_year=locked_dist.academic_year,
                    invoice_number=f"INV-BOOK-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                    issue_date=timezone.localdate(),
                    due_date=timezone.localdate(),
                    total_amount=locked_dist.fee_amount,
                )
                StudentInvoiceItem.objects.create(
                    school=locked_dist.school,
                    invoice=inv,
                    fee_category=cat,
                    description=f"كتاب: {locked_dist.book_title} (عدد {locked_dist.quantity})",
                    amount=locked_dist.fee_amount,
                )
                invoice_entry = post_student_invoice_to_journal(inv)
                if invoice_entry and not inv.journal_entry_id:
                    inv.journal_entry = invoice_entry
                    inv.save(update_fields=["journal_entry", "updated_at"])
                locked_dist.invoice = inv
                self.invoice = inv

            locked_dist._allow_distribution_service_update = True
            locked_dist.delivery_status = self.DeliveryStatus.DELIVERED
            locked_dist.delivered_at = timezone.now()
            if user:
                locked_dist.delivered_by = user
            locked_dist.save(update_fields=["delivery_status", "delivered_at", "delivered_by", "invoice", "updated_at"])
            self.delivery_status = locked_dist.delivery_status
            self.delivered_at = locked_dist.delivered_at
            self.delivered_by = locked_dist.delivered_by
            from apps.auditlog.services import record_event
            record_event(
                action="school_book_distribution.delivered",
                description=f"تسليم {locked_dist.book_title} للطالب {locked_dist.student}",
                actor=user,
                school=locked_dist.school,
                obj=locked_dist,
                metadata={
                    "quantity": str(locked_dist.quantity),
                    "inventory_item_id": str(locked_dist.inventory_item_id or ""),
                    "invoice_id": str(locked_dist.invoice_id or ""),
                },
            )

    def return_book(self, user=None):
        """استرجاع الكتاب إلى المخزون وتحديث حالته والتسوية المالية مع قفل تشاؤمي."""
        from django.db import transaction
        with transaction.atomic():
            locked_dist = StudentBookDistribution.objects.select_for_update().get(pk=self.pk)
            if locked_dist.delivery_status != self.DeliveryStatus.DELIVERED:
                return
            if locked_dist.inventory_item:
                from apps.inventory.services import record_stock_movement
                item = locked_dist.inventory_item
                record_stock_movement(
                    school=locked_dist.school,
                    item=item,
                    warehouse=item.warehouse,
                    movement_type="receipt",
                    quantity=locked_dist.quantity,
                    unit_cost=item.unit_cost,
                    idempotency_key=f"book-return-{locked_dist.pk}",
                    notes=f"استرجاع كتاب من الطالب {locked_dist.student.student_id_number}",
                    recipient_name=f"استرجاع من الطالب: {locked_dist.student}",
                    reference=f"استرجاع كتاب من الطالب {locked_dist.student.student_id_number}",
                    created_by=user,
                )

            # معالجة الأثر المالي عند استرجاع الكتاب
            if locked_dist.invoice_id:
                from apps.student_fees.models import StudentInvoice
                inv = StudentInvoice.objects.select_for_update().get(pk=locked_dist.invoice_id)
                if inv.paid_amount > Decimal("0.00"):
                    raise ValidationError(
                        "لا يمكن استرجاع الكتاب مالياً قبل عكس سندات القبض المرتبطة وإعادة الفاتورة إلى رصيد غير مسدد."
                    )
                if inv.journal_entry_id:
                    from apps.accounting.services.auto_posting import reverse_journal_entry
                    reverse_journal_entry(
                        inv.journal_entry,
                        reason=f"إلغاء رسوم استرجاع الكتاب: {locked_dist.book_title}",
                        reversed_by=user,
                    )
                inv.status = StudentInvoice.Status.CANCELLED
                inv.save(update_fields=["status", "updated_at"])

            locked_dist._allow_distribution_service_update = True
            locked_dist.delivery_status = self.DeliveryStatus.RETURNED
            locked_dist.returned_at = timezone.now()
            if user:
                locked_dist.returned_by = user
            locked_dist.save(update_fields=["delivery_status", "returned_at", "returned_by", "updated_at"])
            self.delivery_status = locked_dist.delivery_status
            self.returned_at = locked_dist.returned_at
            self.returned_by = locked_dist.returned_by
            from apps.auditlog.services import record_event
            record_event(
                action="school_book_distribution.returned",
                description=f"استرجاع {locked_dist.book_title} من الطالب {locked_dist.student}",
                actor=user,
                school=locked_dist.school,
                obj=locked_dist,
                metadata={
                    "quantity": str(locked_dist.quantity),
                    "invoice_id": str(locked_dist.invoice_id or ""),
                },
            )


class BookRequisitionOrder(TenantOwnedModel):
    """
    أمر صرف وطلب توريد كتب من المستودع المدرسي.
    دورة عمل معتمدة: يرفع المعلم أو المشرف الطلب للشعبة، تعتمده الإدارة، ويصرفه أمين المستودع.
    """
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة طلب"
        SUBMITTED = "submitted", "مرفوع للاعتماد الإداري"
        APPROVED = "approved", "معتمد - موجه لأمين المستودع"
        FULFILLED = "fulfilled", "تم الصرف والتسليم من المخزن"
        REJECTED = "rejected", "مرفوض"

    order_number = models.CharField("رقم أمر الصرف", max_length=50, db_index=True)
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="book_orders",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي المستفيد",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="book_orders",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية المستفيدة",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="book_orders",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="محرر الطلب (المشرف / المعلم)",
        on_delete=models.PROTECT,
        related_name="requested_book_orders",
    )
    status = models.CharField("حالة أمر الصرف", max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المسؤول المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_book_orders",
    )
    approved_at = models.DateTimeField("تاريخ الاعتماد الإداري", null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="أمين المستودع الصارف",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfilled_book_orders",
    )
    fulfilled_at = models.DateTimeField("تاريخ الصرف من المخزن", null=True, blank=True)
    notes = models.TextField("ملاحظات أمر الصرف", blank=True)

    class Meta:
        verbose_name = "أمر صرف كتب ومستلزمات"
        verbose_name_plural = "أوامر صرف الكتب من المستودع"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "order_number"],
                condition=models.Q(is_archived=False),
                name="school_services_book_order_uniq",
            )
        ]
        permissions = [
            ("submit_bookrequisitionorder", "يمكنه رفع أمر صرف كتب"),
            ("approve_bookrequisitionorder", "يمكنه اعتماد أمر صرف كتب"),
            ("reject_bookrequisitionorder", "يمكنه رفض أمر صرف كتب"),
            ("fulfill_bookrequisitionorder", "يمكنه تنفيذ صرف أمر الكتب"),
        ]

    def clean(self):
        super().clean()
        if self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "السنة الدراسية لا تتبع المدرسة نفسها."})
        if self.grade_level_id and self.grade_level.school_id != self.school_id:
            raise ValidationError({"grade_level": "الصف لا يتبع المدرسة نفسها."})
        if self.section_id and self.section.school_id != self.school_id:
            raise ValidationError({"section": "الشعبة لا تتبع المدرسة نفسها."})
        if self.requested_by_id and not self.requested_by.school_memberships.filter(
            school_id=self.school_id,
            status="active",
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        ).exists():
            raise ValidationError({"requested_by": "محرر الطلب لا يمتلك عضوية نشطة وسارية في المدرسة."})
        if self.section_id and self.grade_level_id and self.section.grade_id != self.grade_level_id:
            raise ValidationError({"section": "الشعبة لا تتبع الصف المحدد في أمر الصرف."})
        if self.section_id and self.academic_year_id and self.section.academic_year_id != self.academic_year_id:
            raise ValidationError({"section": "الشعبة لا تتبع السنة الدراسية المحددة."})

    def __str__(self) -> str:
        beneficiary = self.section or self.grade_level or "عام"
        return f"أمر صرف #{self.order_number} ({beneficiary}): {self.get_status_display()}"

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if not self._state.adding:
                previous = type(self).objects.select_for_update().filter(
                    pk=self.pk
                ).values(
                    "school_id", "order_number", "academic_year_id",
                    "grade_level_id", "section_id", "requested_by_id", "status",
                    "approved_by_id", "approved_at", "fulfilled_by_id", "fulfilled_at",
                ).first()
                if previous:
                    immutable_fields = (
                        "school_id", "order_number", "academic_year_id",
                        "grade_level_id", "section_id", "requested_by_id",
                    )
                    if any(
                        previous[field] != getattr(self, field)
                        for field in immutable_fields
                    ):
                        raise ValidationError("هوية أمر الصرف والجهة المستفيدة لا تتغير بعد إنشائه.")
                    workflow_fields = (
                        "status", "approved_by_id", "approved_at",
                        "fulfilled_by_id", "fulfilled_at",
                    )
                    if (
                        any(
                            previous[field] != getattr(self, field)
                            for field in workflow_fields
                        )
                        and not getattr(self, "_allow_requisition_workflow_update", False)
                    ):
                        raise ValidationError("حالة أمر الصرف واعتماداته لا تعدل مباشرة؛ استخدم إجراءات سير العمل.")
            return super().save(*args, **kwargs)

    def archive(self, *, actor=None, reason: str = "") -> None:
        if self.status not in {self.Status.DRAFT, self.Status.REJECTED}:
            raise ValidationError("لا تؤرشف أمر صرف مرفوعاً أو معتمداً أو منفذاً.")
        return super().archive(actor=actor, reason=reason)

    def delete(self, *args, **kwargs):
        raise ValidationError("أوامر الصرف تحفظ كسجل تدقيقي ولا تحذف من النظام.")


class BookRequisitionItem(TenantOwnedModel):
    """البنود والكتب المطلوبة في أمر الصرف."""
    requisition = models.ForeignKey(
        BookRequisitionOrder,
        verbose_name="أمر الصرف التابع له",
        on_delete=models.CASCADE,
        related_name="items",
    )
    book_title = models.CharField("اسم الكتاب / المادة المنهجية", max_length=200)
    quantity_requested = models.PositiveIntegerField("الكمية المطلوبة (نسخ)")
    quantity_approved = models.PositiveIntegerField("الكمية المعتمدة", default=0)
    quantity_dispatched = models.PositiveIntegerField("الكمية المصروفة فعلياً", default=0)
    notes = models.CharField("ملاحظات البند", max_length=255, blank=True)

    class Meta:
        verbose_name = "بند أمر صرف كتب"
        verbose_name_plural = "بنود أوامر صرف الكتب"

    def clean(self):
        super().clean()
        if self.requisition_id and self.requisition.school_id != self.school_id:
            raise ValidationError({"requisition": "أمر الصرف لا يتبع المدرسة نفسها."})
        if self.quantity_requested < 1:
            raise ValidationError({"quantity_requested": "الكمية المطلوبة يجب أن تكون موجبة."})
        if not 0 <= self.quantity_dispatched <= self.quantity_approved <= self.quantity_requested:
            raise ValidationError("يجب أن تكون الكميات المصروفة والمعتمدة ضمن حدود الكمية المطلوبة.")

    def __str__(self) -> str:
        return f"{self.book_title}: {self.quantity_dispatched}/{self.quantity_requested} نسخة"

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if not self._state.adding:
                previous = type(self).objects.select_for_update().filter(
                    pk=self.pk
                ).values(
                    "school_id", "requisition_id", "book_title",
                    "quantity_requested", "quantity_approved",
                    "quantity_dispatched", "notes",
                ).first()
                if previous:
                    if (
                        previous["school_id"] != self.school_id
                        or previous["requisition_id"] != self.requisition_id
                    ):
                        raise ValidationError("لا تنقل بند أمر الصرف إلى مدرسة أو طلب آخر.")
                    requisition = BookRequisitionOrder.objects.select_for_update().get(
                        pk=self.requisition_id
                    )
                    if requisition.status != BookRequisitionOrder.Status.DRAFT:
                        if any(
                            previous[field] != getattr(self, field)
                            for field in ("book_title", "quantity_requested", "notes")
                        ):
                            raise ValidationError("تفاصيل بند أمر الصرف تقفل بعد رفع الطلب.")
                        if (
                            previous["quantity_approved"] != self.quantity_approved
                            and not getattr(self, "_allow_requisition_approval_update", False)
                        ):
                            raise ValidationError("كمية الاعتماد لا تعدل خارج إجراء اعتماد أمر الصرف.")
                        if (
                            previous["quantity_dispatched"] != self.quantity_dispatched
                            and not getattr(self, "_allow_requisition_fulfilment_update", False)
                        ):
                            raise ValidationError("الكمية المصروفة لا تعدل خارج إجراء الصرف المخزني.")
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.requisition.status != BookRequisitionOrder.Status.DRAFT:
            raise ValidationError("لا تحذف بنود أمر صرف مرفوع أو معتمد.")
        return super().delete(*args, **kwargs)


class BookRequisitionFulfillment(TenantOwnedModel):
    """Immutable request receipt for replay-safe partial or full fulfilment."""
    requisition = models.ForeignKey(
        BookRequisitionOrder,
        verbose_name="أمر الصرف",
        on_delete=models.PROTECT,
        related_name="fulfillment_batches",
    )
    idempotency_key = models.CharField("مفتاح منع تكرار طلب الصرف", max_length=80)
    payload_hash = models.CharField("بصمة بيانات الصرف", max_length=64)
    line_count = models.PositiveSmallIntegerField("عدد البنود المصروفة")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="نفذ الصرف",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="book_requisition_fulfillments",
    )

    class Meta:
        verbose_name = "دفعة تنفيذ أمر صرف كتب"
        verbose_name_plural = "دفعات تنفيذ أوامر صرف الكتب"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="school_services_requisition_fulfil_key_uniq",
            )
        ]

    def clean(self):
        super().clean()
        if self.requisition_id and self.requisition.school_id != self.school_id:
            raise ValidationError({"requisition": "أمر الصرف لا يتبع المدرسة نفسها."})
        if not 8 <= len(self.idempotency_key) <= 80:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب أن يكون بين 8 و80 حرفاً."})
        if len(self.payload_hash) != 64:
            raise ValidationError({"payload_hash": "بصمة طلب الصرف غير صالحة."})
        if self.line_count < 1:
            raise ValidationError({"line_count": "دفعة الصرف يجب أن تحتوي بنداً واحداً على الأقل."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("دفعة تنفيذ أمر الصرف سجل تدقيقي لا يجوز تعديله.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا تحذف دفعات تنفيذ أوامر الصرف؛ استخدم العكس المخزني المعتمد.")


# -----------------------------------------------------------------------------
# Legacy clinic tables retained for historical data compatibility only.
# They are intentionally not registered in school admin or the API.
# -----------------------------------------------------------------------------

class StudentHealthProfile(TenantOwnedModel):
    """الملف الصحي والوقائي للطالب والتنبيهات المرضية."""
    student = models.OneToOneField(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    blood_type = models.CharField("فصيلة الدم", max_length=10, blank=True)
    chronic_conditions = models.TextField("الأمراض المزمنة (إن وجدت)", blank=True)
    allergies = models.TextField("الحساسية الدوائية أو الغذائية", blank=True)
    daily_medications = models.TextField("الأدوية اليومية والجرعات", blank=True)
    emergency_contact_name = models.CharField("اسم جهة الاتصال للطوارئ", max_length=120)
    emergency_contact_phone = models.CharField("هاتف الطوارئ البديل", max_length=30)
    general_notes = models.TextField("ملاحظات صحية عامة وتوصيات", blank=True)

    class Meta:
        verbose_name = "ملف صحي لطالب"
        verbose_name_plural = "الملفات الصحية للطلاب"

    def __str__(self) -> str:
        return f"الملف الصحي - {self.student}: {self.blood_type or 'غير محدد'}"


class ClinicVisit(TenantOwnedModel):
    """زيارات العيادة المدرسية والإسعافات الأولية."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب المراجع",
        on_delete=models.CASCADE,
        related_name="clinic_visits",
    )
    visit_date = models.DateTimeField("تاريخ ووقت الزيارة", default=timezone.now)
    symptoms = models.TextField("الأعراض والشكوى")
    diagnosis = models.TextField("التشخيص التقديري", blank=True)
    treatment_given = models.TextField("الإسعافات أو العلاج المقدم", blank=True)
    temperature = models.DecimalField("درجة الحرارة (إن قيست)", max_digits=4, decimal_places=1, null=True, blank=True)
    sent_home = models.BooleanField("تم صرف الطالب إلى المنزل", default=False)
    parent_notified = models.BooleanField("تم إشعار ولي الأمر هاتفياً / رسالة", default=False)
    attended_by = models.CharField("المشرف / الممرض المعالج", max_length=120, blank=True)
    notes = models.TextField("ملاحظات إضافية وتوصيات للمتابعة", blank=True)

    class Meta:
        verbose_name = "زيارة عيادة مدرسية"
        verbose_name_plural = "سجل زيارات العيادة المدرسية"

    def __str__(self) -> str:
        return f"زيارة عيادة: {self.student} - {self.visit_date.strftime('%Y-%m-%d %H:%M')}"
