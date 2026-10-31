"""Identity, tenant membership, role assignment and platform access."""
from __future__ import annotations

import hashlib
import re
import secrets

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Permission, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import ArchivableModel, UUIDTimestampedModel


def normalize_phone(value: str) -> str:
    return "".join(ch for ch in (value or "").strip() if ch not in " ()-.")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone: str, password: str | None = None, **extra_fields):
        if not phone:
            raise ValueError("رقم الهاتف مطلوب لإنشاء الحساب.")
        phone = normalize_phone(phone)
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password", "last_login", "groups", "user_permissions"])
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_admin", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("حساب مدير المنصة يجب أن يمتلك is_staff و is_superuser.")
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, UUIDTimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "نشط"
        SUSPENDED = "suspended", "موقوف"
        PENDING = "pending", "بانتظار التفعيل"

    phone = models.CharField("رقم الهاتف", max_length=20, unique=True, db_index=True)
    email = models.EmailField("البريد الإلكتروني", blank=True)
    first_name = models.CharField("الاسم الأول", max_length=100)
    middle_name = models.CharField("اسم الأب", max_length=100, blank=True)
    last_name = models.CharField("اسم العائلة", max_length=100)
    full_name = models.CharField("الاسم الكامل", max_length=305, blank=True, db_index=True)
    preferred_language = models.CharField("لغة الواجهة", max_length=8, default="ar", choices=[("ar", "العربية"), ("en", "English")])
    timezone = models.CharField("المنطقة الزمنية", max_length=64, default="Asia/Aden")
    avatar = models.ImageField("الصورة الشخصية", upload_to="identity/avatars/%Y/%m/", blank=True)
    status = models.CharField("حالة الحساب", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_active = models.BooleanField("الحساب مفعل", default=True)
    is_staff = models.BooleanField("دخول لوحة الإدارة", default=False)
    is_platform_admin = models.BooleanField("مدير منصة", default=False, db_index=True)
    phone_verified_at = models.DateTimeField("تاريخ توثيق الهاتف", null=True, blank=True)
    email_verified_at = models.DateTimeField("تاريخ توثيق البريد", null=True, blank=True)
    last_seen_at = models.DateTimeField("آخر نشاط", null=True, blank=True)
    failed_login_count = models.PositiveSmallIntegerField("محاولات الدخول الفاشلة", default=0)
    locked_until = models.DateTimeField("الحساب مقفل حتى", null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "مستخدم"
        verbose_name_plural = "المستخدمون"
        ordering = ["first_name", "last_name"]
        indexes = [models.Index(fields=["status", "is_active"])]
        constraints = [
            models.UniqueConstraint(fields=["email"], condition=~Q(email=""), name="accounts_user_unique_nonempty_email"),
        ]

    def __str__(self):
        return self.full_name or f"{self.first_name} {self.last_name}".strip() or self.phone

    def get_full_name(self) -> str:
        return self.full_name or f"{self.first_name} {self.last_name}".strip() or self.phone

    def get_short_name(self) -> str:
        return self.first_name or self.phone

    def clean(self):
        super().clean()
        self.phone = normalize_phone(self.phone)
        self.email = (self.email or "").strip().lower()
        self.full_name = " ".join(part for part in [self.first_name, self.middle_name, self.last_name] if part).strip()
        if self.phone and not re.fullmatch(r"\+?[1-9]\d{7,14}", self.phone):
            raise ValidationError({"phone": "أدخل رقم هاتف دولياً بصيغة صحيحة، مثل +9677XXXXXXX."})

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        self.email = (self.email or "").strip().lower()
        self.full_name = " ".join(part for part in [self.first_name, self.middle_name, self.last_name] if part).strip()
        # Keep Django's authentication flag aligned with explicit account suspension.
        if self.status != self.Status.ACTIVE:
            self.is_active = False
        elif self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous_status and previous_status != self.status:
                self.is_active = True
        return super().save(*args, **kwargs)

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())


class DeviceSession(UUIDTimestampedModel):
    """Revocable per-device API session; only a digest of the bearer secret is stored."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_sessions",
    )
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    device_id = models.CharField(max_length=128)
    device_name = models.CharField(max_length=120, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "جلسة جهاز"
        verbose_name_plural = "جلسات الأجهزة"
        indexes = [
            models.Index(fields=["user", "revoked_at", "expires_at"]),
            models.Index(fields=["user", "device_id", "revoked_at"]),
        ]

    @property
    def is_active(self) -> bool:
        return (
            self.revoked_at is None
            and self.expires_at > timezone.now()
            and self.user.is_active
            and self.user.status == User.Status.ACTIVE
        )


class PhoneVerificationChallenge(UUIDTimestampedModel):
    """Short-lived, purpose-bound OTP challenge. The raw code is never persisted."""

    class Purpose(models.TextChoices):
        VERIFY_PHONE = "verify_phone", "توثيق رقم الهاتف"
        PASSWORD_RESET = "password_reset", "استعادة كلمة المرور"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_verification_challenges",
    )
    phone = models.CharField(max_length=20, db_index=True)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, db_index=True)
    code_digest = models.CharField(max_length=64, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "طلب رمز تحقق"
        verbose_name_plural = "طلبات رموز التحقق"
        indexes = [
            models.Index(fields=["user", "purpose", "created_at"]),
            models.Index(fields=["phone", "purpose", "created_at"]),
        ]


class PlatformAccess(UUIDTimestampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "مالك المنصة"
        OPERATIONS = "operations", "مدير التشغيل"
        SUPPORT = "support", "الدعم الفني"
        BILLING = "billing", "إدارة الاشتراكات"
        AUDITOR = "auditor", "مراجع"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="المستخدم", on_delete=models.CASCADE, related_name="platform_accesses")
    role = models.CharField("الدور المركزي", max_length=20, choices=Role.choices)
    permissions = models.ManyToManyField(Permission, verbose_name="صلاحيات المنصة الإضافية", blank=True, related_name="platform_access_grants")
    is_active = models.BooleanField("مفعل", default=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="منح الصلاحية بواسطة", null=True, blank=True, on_delete=models.SET_NULL, related_name="granted_platform_accesses")
    notes = models.CharField("ملاحظات", max_length=500, blank=True)

    class Meta:
        verbose_name = "صلاحية مركزية"
        verbose_name_plural = "صلاحيات المنصة المركزية"
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="accounts_platformaccess_user_role_uniq")]

    def __str__(self):
        return f"{self.user} - {self.get_role_display()}"


class SchoolMembership(UUIDTimestampedModel):
    class Status(models.TextChoices):
        INVITED = "invited", "مدعو"
        ACTIVE = "active", "نشط"
        SUSPENDED = "suspended", "موقوف"
        LEFT = "left", "غادر"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="المستخدم", on_delete=models.PROTECT, related_name="school_memberships")
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.INVITED, db_index=True)
    is_default = models.BooleanField("المدرسة الافتراضية", default=False)
    joined_at = models.DateTimeField("تاريخ الانضمام", null=True, blank=True)
    expires_at = models.DateTimeField("انتهاء العضوية", null=True, blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="دعا بواسطة", null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_school_invitations")
    notes = models.CharField("ملاحظات داخلية", max_length=500, blank=True)

    class Meta:
        verbose_name = "عضوية مدرسة"
        verbose_name_plural = "عضويات المدارس"
        ordering = ["school__name", "user__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "user"], name="accounts_membership_school_user_uniq"),
            models.UniqueConstraint(fields=["user"], condition=Q(is_default=True, status="active"), name="accounts_one_default_active_school_per_user"),
        ]
        indexes = [models.Index(fields=["school", "status"]), models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.user} @ {self.school}"

    @property
    def roles(self):
        """إرجاع كشف الأدوار المسندة للعضوية."""
        return SchoolRole.objects.filter(assignments__membership=self, is_active=True)

    def get_role_codes(self) -> set[str]:
        """إرجاع أكواد الأدوار الصالحة للعضوية لمطابقة الصلاحيات."""
        today = timezone.localdate()
        return set(
            self.role_assignments.filter(
                role__is_active=True,
                valid_from__lte=today,
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=today)
            ).values_list("role__code", flat=True)
        )

    def activate(self):
        self.status = self.Status.ACTIVE
        self.joined_at = self.joined_at or timezone.now()
        self.save(update_fields=["status", "joined_at", "updated_at"])

    def clean(self):
        super().clean()
        if self.expires_at and self.joined_at and self.expires_at < self.joined_at:
            raise ValidationError({"expires_at": "تاريخ انتهاء العضوية لا يسبق تاريخ الانضمام."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SchoolRole(UUIDTimestampedModel, ArchivableModel):
    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", on_delete=models.CASCADE, related_name="roles")
    code = models.SlugField("رمز الدور", max_length=60)
    name = models.CharField("اسم الدور", max_length=100)
    description = models.TextField("الوصف", blank=True)
    permissions = models.ManyToManyField(Permission, verbose_name="الصلاحيات", blank=True, related_name="school_roles")
    is_system = models.BooleanField("دور أساسي", default=False)
    is_active = models.BooleanField("مفعل", default=True)

    class Meta:
        verbose_name = "دور مدرسي"
        verbose_name_plural = "الأدوار المدرسية"
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="accounts_schoolrole_school_code_uniq")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.school})"


class MembershipRole(UUIDTimestampedModel):
    membership = models.ForeignKey(SchoolMembership, verbose_name="العضوية", on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(SchoolRole, verbose_name="الدور", on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="أسند بواسطة", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_school_roles")
    valid_from = models.DateField("صالح من", default=timezone.localdate)
    valid_until = models.DateField("صالح حتى", null=True, blank=True)

    class Meta:
        verbose_name = "إسناد دور"
        verbose_name_plural = "إسنادات الأدوار"
        constraints = [models.UniqueConstraint(fields=["membership", "role"], name="accounts_membership_role_uniq")]

    def clean(self):
        super().clean()
        if self.membership_id and self.role_id:
            membership_school = self.membership.school_id
            role_school = self.role.school_id
            if membership_school != role_school:
                raise ValidationError("لا يجوز إسناد دور تابع لمدرسة مختلفة عن مدرسة العضوية.")
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "تاريخ انتهاء الدور يجب ألا يسبق تاريخ بدايته."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SchoolInvitation(UUIDTimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "بانتظار القبول"
        ACCEPTED = "accepted", "مقبولة"
        EXPIRED = "expired", "منتهية"
        REVOKED = "revoked", "ملغاة"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField("البريد المدعو", blank=True)
    phone = models.CharField("رقم الهاتف", max_length=20, blank=True)
    token_digest = models.CharField("بصمة رمز الدعوة", max_length=64, unique=True, editable=False)
    status = models.CharField("حالة الدعوة", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField("تنتهي في")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="المرسل", on_delete=models.PROTECT, related_name="school_invitations")
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="قبلها", null=True, blank=True, on_delete=models.SET_NULL, related_name="accepted_school_invitations")
    accepted_at = models.DateTimeField("تاريخ القبول", null=True, blank=True)
    roles = models.ManyToManyField(SchoolRole, verbose_name="الأدوار الممنوحة", blank=True, related_name="invitations")
    message = models.CharField("رسالة الدعوة", max_length=500, blank=True)

    class Meta:
        verbose_name = "دعوة انضمام"
        verbose_name_plural = "دعوات الانضمام"
        indexes = [models.Index(fields=["school", "status", "expires_at"])]

    def __str__(self):
        return f"{self.email} - {self.school}"

    @classmethod
    def create_invitation(cls, **kwargs):
        raw_token = secrets.token_urlsafe(36)
        instance = cls(token_digest=hashlib.sha256(raw_token.encode()).hexdigest(), **kwargs)
        instance.full_clean()
        instance.save()
        return instance, raw_token

    def matches_token(self, raw_token: str) -> bool:
        return secrets.compare_digest(self.token_digest, hashlib.sha256(raw_token.encode()).hexdigest())
