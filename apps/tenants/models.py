"""School tenant registry, branches, custom domains and school settings."""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from apps.core.models import ArchivableModel, UUIDTimestampedModel

CODE_VALIDATOR = RegexValidator(r"^[A-Z0-9][A-Z0-9_-]{2,19}$", "استخدم 3-20 حرفاً أو رقماً أو الشرطة.")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$")


class School(UUIDTimestampedModel, ArchivableModel):
    class Type(models.TextChoices):
        PRIVATE = "private", "أهلية / خاصة"
        PUBLIC = "public", "حكومية"
        KINDERGARTEN = "kindergarten", "روضة أطفال"
        INSTITUTE = "institute", "معهد"
        TRAINING = "training", "مركز تدريب"
        COMPLEX = "complex", "مجمع تعليمي"
        OTHER = "other", "أخرى"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        ACTIVE = "active", "نشطة"
        SUSPENDED = "suspended", "موقوفة"
        ARCHIVED = "archived", "مؤرشفة"

    owner = models.ForeignKey("accounts.User", verbose_name="مدير / مالك المدرسة", on_delete=models.PROTECT, related_name="owned_schools")
    code = models.CharField("كود المدرسة", max_length=20, unique=True, validators=[CODE_VALIDATOR], db_index=True)
    name = models.CharField("اسم المدرسة", max_length=180, db_index=True)
    slug = models.SlugField("المعرف اللطيف", max_length=190, unique=True, blank=True)
    legal_name = models.CharField("الاسم القانوني", max_length=220, blank=True)
    school_type = models.CharField("نوع المؤسسة", max_length=20, choices=Type.choices, default=Type.PRIVATE)
    status = models.CharField("حالة المدرسة", max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    logo = models.ImageField("الشعار", upload_to="schools/logos/%Y/%m/", blank=True)
    brand_primary = models.CharField("اللون الأساسي", max_length=7, default="#1D4ED8")
    brand_secondary = models.CharField("اللون المساند", max_length=7, default="#0F172A")
    country_code = models.CharField("رمز الدولة", max_length=2, default="YE")
    city = models.CharField("المدينة", max_length=100, blank=True)
    address = models.TextField("العنوان", blank=True)
    phone = models.CharField("الهاتف", max_length=20, blank=True)
    email = models.EmailField("البريد الرسمي", blank=True)
    website = models.URLField("الموقع الإلكتروني", blank=True)
    timezone = models.CharField("المنطقة الزمنية", max_length=64, default="Asia/Aden")
    language_code = models.CharField("لغة المدرسة", max_length=8, default="ar", choices=[("ar", "العربية"), ("en", "English")])
    currency_code = models.CharField("العملة الأساسية", max_length=3, default="YER")
    established_on = models.DateField("تاريخ التأسيس", null=True, blank=True)
    activated_at = models.DateTimeField("تاريخ التفعيل", null=True, blank=True)
    suspended_at = models.DateTimeField("تاريخ الإيقاف", null=True, blank=True)
    platform_notes = models.TextField("ملاحظات المنصة الداخلية", blank=True)

    class Meta:
        verbose_name = "مدرسة"
        verbose_name_plural = "المدارس والمؤسسات"
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "school_type"]), models.Index(fields=["city", "status"])]

    def __str__(self):
        return f"{self.name} [{self.code}]"

    def clean(self):
        super().clean()
        self.code = self.code.upper().strip()
        if not self.slug:
            self.slug = slugify(self.code) or self.code.lower()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.brand_primary):
            raise ValidationError({"brand_primary": "أدخل لوناً بصيغة HEX مثل #1D4ED8."})
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.brand_secondary):
            raise ValidationError({"brand_secondary": "أدخل لوناً بصيغة HEX مثل #0F172A."})

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        if not self.slug:
            self.slug = slugify(self.code) or self.code.lower()
        self.full_clean()
        return super().save(*args, **kwargs)


class Branch(UUIDTimestampedModel, ArchivableModel):
    school = models.ForeignKey(School, verbose_name="المدرسة", on_delete=models.PROTECT, related_name="branches")
    code = models.CharField("كود الفرع", max_length=20, validators=[CODE_VALIDATOR])
    name = models.CharField("اسم الفرع", max_length=150)
    is_main = models.BooleanField("الفرع الرئيسي", default=False)
    status = models.CharField("الحالة", max_length=12, choices=[("active", "نشط"), ("inactive", "غير نشط")], default="active")
    phone = models.CharField("الهاتف", max_length=20, blank=True)
    address = models.TextField("العنوان", blank=True)
    manager_name = models.CharField("اسم المسؤول", max_length=150, blank=True)
    capacity = models.PositiveIntegerField("الطاقة الاستيعابية", null=True, blank=True)

    class Meta:
        verbose_name = "فرع"
        verbose_name_plural = "فروع المدارس"
        ordering = ["school__name", "-is_main", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="tenants_branch_school_code_uniq"),
            models.UniqueConstraint(fields=["school"], condition=Q(is_main=True, is_archived=False), name="tenants_one_main_branch_per_school"),
        ]
        indexes = [models.Index(fields=["school", "status"])]

    def __str__(self):
        return f"{self.school.code} / {self.name}"

    def clean(self):
        super().clean()
        self.code = self.code.upper().strip()
        if not self.code:
            raise ValidationError({"code": "كود الفرع مطلوب."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SchoolDomain(UUIDTimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "بانتظار التحقق"
        VERIFIED = "verified", "موثق"
        DISABLED = "disabled", "معطل"

    school = models.ForeignKey(School, verbose_name="المدرسة", on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField("النطاق", max_length=253, unique=True)
    is_primary = models.BooleanField("النطاق الأساسي", default=False)
    status = models.CharField("حالة النطاق", max_length=10, choices=Status.choices, default=Status.PENDING)
    verification_token = models.CharField("رمز التحقق", max_length=64, blank=True)
    verified_at = models.DateTimeField("تاريخ التحقق", null=True, blank=True)

    class Meta:
        verbose_name = "نطاق مدرسة"
        verbose_name_plural = "نطاقات المدارس"
        constraints = [models.UniqueConstraint(fields=["school"], condition=Q(is_primary=True), name="tenants_one_primary_domain_per_school")]

    def __str__(self):
        return self.domain

    def clean(self):
        super().clean()
        self.domain = self.domain.strip().lower().rstrip(".")
        if not DOMAIN_RE.fullmatch(self.domain):
            raise ValidationError({"domain": "أدخل اسم نطاق صحيحاً مثل school.example.com."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SchoolSettings(UUIDTimestampedModel):
    """Structured extension point for school preferences; avoid arbitrary business data here."""
    school = models.OneToOneField(School, verbose_name="المدرسة", on_delete=models.CASCADE, related_name="settings")
    allow_guardian_multiple_children = models.BooleanField("السماح بربط عدة أبناء بولي الأمر", default=True)
    require_student_photo = models.BooleanField("إلزام صورة الطالب", default=False)
    require_admission_approval = models.BooleanField("اعتماد طلبات القبول", default=True)
    attendance_lock_after_days = models.PositiveSmallIntegerField("قفل تعديل الحضور بعد (أيام)", default=7)
    default_lesson_minutes = models.PositiveSmallIntegerField("مدة الحصة الافتراضية بالدقائق", default=45)
    notification_channels = models.JSONField("قنوات الإشعار المفعلة", default=list, blank=True)
    feature_overrides = models.JSONField("تجاوزات المزايا", default=dict, blank=True)

    class Meta:
        verbose_name = "إعدادات المدرسة"
        verbose_name_plural = "إعدادات المدارس"

    def __str__(self):
        return f"إعدادات {self.school.name}"

