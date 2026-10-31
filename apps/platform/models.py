"""Central platform catalog and subscription billing, never school ledgers."""
from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import UUIDTimestampedModel


class Feature(UUIDTimestampedModel):
    code = models.SlugField("رمز الميزة", max_length=80, unique=True)
    name = models.CharField("اسم الميزة", max_length=120)
    description = models.TextField("الوصف", blank=True)
    module_key = models.CharField("مفتاح الوحدة", max_length=80)
    is_active = models.BooleanField("مفعلة على المنصة", default=True)
    is_addon = models.BooleanField("إضافة اختيارية", default=False)

    class Meta:
        verbose_name = "ميزة منصة"
        verbose_name_plural = "كتالوج المزايا"
        ordering = ["module_key", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Plan(UUIDTimestampedModel):
    class Cycle(models.TextChoices):
        MONTHLY = "monthly", "شهري"
        QUARTERLY = "quarterly", "ربع سنوي"
        YEARLY = "yearly", "سنوي"
        CUSTOM = "custom", "مخصص"

    code = models.SlugField("رمز الباقة", max_length=60, unique=True)
    name = models.CharField("اسم الباقة", max_length=120)
    description = models.TextField("الوصف", blank=True)
    billing_cycle = models.CharField("دورة الفوترة الافتراضية", max_length=12, choices=Cycle.choices, default=Cycle.YEARLY)
    price = models.DecimalField("السعر الأساسي", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency_code = models.CharField("العملة", max_length=3, default="YER")
    trial_days = models.PositiveSmallIntegerField("أيام التجربة", default=0)
    max_students = models.PositiveIntegerField("الحد الأقصى للطلاب", null=True, blank=True)
    max_staff = models.PositiveIntegerField("الحد الأقصى للموظفين", null=True, blank=True)
    max_branches = models.PositiveSmallIntegerField("الحد الأقصى للفروع", default=1)
    storage_limit_mb = models.PositiveIntegerField("مساحة الملفات بالميجابايت", default=1024)
    limits = models.JSONField("حدود إضافية", default=dict, blank=True)
    is_public = models.BooleanField("تظهر للعملاء", default=True)
    is_active = models.BooleanField("متاحة للاشتراك", default=True)
    display_order = models.PositiveSmallIntegerField("ترتيب العرض", default=0)

    class Meta:
        verbose_name = "باقة اشتراك"
        verbose_name_plural = "باقات المنصة"
        ordering = ["display_order", "price"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.price < 0:
            raise ValidationError({"price": "لا يمكن أن يكون سعر الباقة سالباً."})
        if self.max_branches < 1:
            raise ValidationError({"max_branches": "يجب أن تسمح الباقة بفرع واحد على الأقل."})


class PlanFeature(UUIDTimestampedModel):
    plan = models.ForeignKey(Plan, verbose_name="الباقة", on_delete=models.CASCADE, related_name="feature_links")
    feature = models.ForeignKey(Feature, verbose_name="الميزة", on_delete=models.PROTECT, related_name="plan_links")
    is_included = models.BooleanField("مشمولة", default=True)
    limit_value = models.PositiveIntegerField("حد الميزة", null=True, blank=True)
    configuration = models.JSONField("إعدادات الميزة", default=dict, blank=True)

    class Meta:
        verbose_name = "ميزة ضمن باقة"
        verbose_name_plural = "مزايا الباقات"
        constraints = [models.UniqueConstraint(fields=["plan", "feature"], name="platform_plan_feature_uniq")]

    def __str__(self):
        return f"{self.plan} - {self.feature}"


class Subscription(UUIDTimestampedModel):
    class Status(models.TextChoices):
        TRIAL = "trial", "تجريبية"
        ACTIVE = "active", "نشطة"
        PAST_DUE = "past_due", "متأخرة السداد"
        SUSPENDED = "suspended", "موقوفة"
        CANCELLED = "cancelled", "ملغاة"
        EXPIRED = "expired", "منتهية"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", on_delete=models.PROTECT, related_name="platform_subscriptions")
    plan = models.ForeignKey(Plan, verbose_name="الباقة", on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.TRIAL, db_index=True)
    starts_at = models.DateTimeField("تبدأ في")
    ends_at = models.DateTimeField("تنتهي في")
    trial_ends_at = models.DateTimeField("نهاية التجربة", null=True, blank=True)
    cancelled_at = models.DateTimeField("تاريخ الإلغاء", null=True, blank=True)
    suspended_at = models.DateTimeField("تاريخ الإيقاف", null=True, blank=True)
    auto_renew = models.BooleanField("تجديد تلقائي", default=False)
    price_locked = models.DecimalField("السعر المتفق عليه", max_digits=14, decimal_places=2)
    currency_code = models.CharField("العملة", max_length=3, default="YER")
    external_reference = models.CharField("مرجع خارجي", max_length=120, blank=True)
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        verbose_name = "اشتراك مدرسة"
        verbose_name_plural = "اشتراكات المدارس"
        ordering = ["-starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["school"],
                condition=Q(status__in=["trial", "active", "past_due", "suspended"]),
                name="platform_one_open_subscription_per_school",
            )
        ]
        indexes = [models.Index(fields=["status", "ends_at"]), models.Index(fields=["school", "status"])]

    def __str__(self):
        return f"{self.school} - {self.plan}"

    def clean(self):
        super().clean()
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "نهاية الاشتراك يجب أن تكون بعد بدايته."})
        if self.price_locked < 0:
            raise ValidationError({"price_locked": "السعر المتفق عليه لا يمكن أن يكون سالباً."})


class SchoolFeatureOverride(UUIDTimestampedModel):
    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", on_delete=models.CASCADE, related_name="feature_overrides")
    feature = models.ForeignKey(Feature, verbose_name="الميزة", on_delete=models.PROTECT, related_name="school_overrides")
    is_enabled = models.BooleanField("مفعلة للمدرسة", default=True)
    limit_value = models.PositiveIntegerField("حد مخصص", null=True, blank=True)
    starts_at = models.DateTimeField("بداية السريان", null=True, blank=True)
    ends_at = models.DateTimeField("نهاية السريان", null=True, blank=True)
    reason = models.CharField("سبب التجاوز", max_length=300)
    granted_by = models.ForeignKey("accounts.User", verbose_name="منح بواسطة", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "تجاوز ميزة مدرسة"
        verbose_name_plural = "تجاوزات مزايا المدارس"
        constraints = [models.UniqueConstraint(fields=["school", "feature"], name="platform_school_feature_override_uniq")]

    def __str__(self):
        return f"{self.school} - {self.feature}"

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError("نهاية سريان الميزة يجب أن تكون بعد بدايتها.")


class PlatformInvoice(UUIDTimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        ISSUED = "issued", "صادرة"
        PARTIAL = "partial", "مدفوعة جزئياً"
        PAID = "paid", "مدفوعة"
        OVERDUE = "overdue", "متأخرة"
        VOID = "void", "ملغاة"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", on_delete=models.PROTECT, related_name="platform_invoices")
    subscription = models.ForeignKey(Subscription, verbose_name="الاشتراك", on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField("رقم فاتورة المنصة", max_length=40, unique=True)
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    issue_date = models.DateField("تاريخ الإصدار")
    due_date = models.DateField("تاريخ الاستحقاق")
    subtotal = models.DecimalField("الإجمالي قبل الخصم والضريبة", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField("الخصم", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField("الضريبة", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField("الإجمالي", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField("المدفوع", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency_code = models.CharField("العملة", max_length=3, default="YER")
    issued_at = models.DateTimeField("تاريخ الاعتماد", null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        verbose_name = "فاتورة اشتراك منصة"
        verbose_name_plural = "فواتير اشتراكات المنصة"
        ordering = ["-issue_date", "-created_at"]
        indexes = [models.Index(fields=["school", "status", "due_date"])]

    def __str__(self):
        return self.number

    @property
    def balance_due(self):
        return self.total - self.paid_amount

    def clean(self):
        super().clean()
        if self.subscription_id and self.school_id and self.subscription.school_id != self.school_id:
            raise ValidationError({"subscription": "الاشتراك لا يتبع المدرسة المحددة."})
        if min(self.subtotal, self.discount_amount, self.tax_amount, self.total, self.paid_amount) < 0:
            raise ValidationError("قيم الفاتورة لا يمكن أن تكون سالبة.")
        if self.discount_amount > self.subtotal:
            raise ValidationError({"discount_amount": "الخصم أكبر من الإجمالي قبل الخصم."})
        expected_total = self.subtotal - self.discount_amount + self.tax_amount
        if self.total != expected_total:
            raise ValidationError({"total": "إجمالي الفاتورة يجب أن يساوي المجموع ناقص الخصم مضافاً إليه الضريبة."})
        if self.paid_amount > self.total:
            raise ValidationError({"paid_amount": "المبلغ المدفوع لا يمكن أن يتجاوز إجمالي الفاتورة."})


class PlatformPayment(UUIDTimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "قيد المعالجة"
        SUCCEEDED = "succeeded", "ناجحة"
        FAILED = "failed", "فاشلة"
        REFUNDED = "refunded", "مستردة"

    invoice = models.ForeignKey(PlatformInvoice, verbose_name="الفاتورة", on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField("المبلغ", max_digits=14, decimal_places=2)
    currency_code = models.CharField("العملة", max_length=3, default="YER")
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    method = models.CharField("طريقة الدفع", max_length=40, blank=True)
    provider = models.CharField("مزود الدفع", max_length=60, blank=True)
    provider_reference = models.CharField("مرجع المزود", max_length=120, blank=True)
    paid_at = models.DateTimeField("وقت الدفع", null=True, blank=True)
    response_payload = models.JSONField("بيانات استجابة المزود", default=dict, blank=True)

    class Meta:
        verbose_name = "دفعة اشتراك المنصة"
        verbose_name_plural = "دفعات اشتراكات المنصة"
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.invoice.number} - {self.amount}"

    def clean(self):
        super().clean()
        if self.amount <= 0:
            raise ValidationError({"amount": "يجب أن يكون مبلغ الدفعة أكبر من صفر."})
        if self.invoice_id and self.currency_code != self.invoice.currency_code:
            raise ValidationError({"currency_code": "عملة الدفعة يجب أن تطابق عملة الفاتورة."})
