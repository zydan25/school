"""In-app messages and transactional outbox foundation."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import UUIDTimestampedModel


class NotificationTemplate(UUIDTimestampedModel):
    class Channel(models.TextChoices):
        IN_APP = "in_app", "داخل النظام"
        EMAIL = "email", "البريد الإلكتروني"
        SMS = "sms", "رسالة نصية"
        WHATSAPP = "whatsapp", "واتساب"
        PUSH = "push", "إشعار التطبيق"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة (فارغ = قالب مركزي)", null=True, blank=True, on_delete=models.CASCADE, related_name="notification_templates")
    code = models.SlugField("رمز القالب", max_length=100)
    channel = models.CharField("القناة", max_length=12, choices=Channel.choices)
    language_code = models.CharField("اللغة", max_length=8, default="ar")
    title_template = models.CharField("قالب العنوان", max_length=250, blank=True)
    body_template = models.TextField("قالب الرسالة")
    variables_schema = models.JSONField("المتغيرات المسموحة", default=dict, blank=True)
    is_active = models.BooleanField("مفعل", default=True)

    class Meta:
        verbose_name = "قالب إشعار"
        verbose_name_plural = "قوالب الإشعارات"
        constraints = [
            models.UniqueConstraint(fields=["school", "code", "channel", "language_code"], condition=Q(school__isnull=False), name="notifications_school_template_uniq"),
            models.UniqueConstraint(fields=["code", "channel", "language_code"], condition=Q(school__isnull=True), name="notifications_global_template_uniq"),
        ]

    def __str__(self):
        return f"{self.code} / {self.get_channel_display()}"


class Notification(UUIDTimestampedModel):
    class Channel(models.TextChoices):
        IN_APP = "in_app", "داخل النظام"
        EMAIL = "email", "البريد الإلكتروني"
        SMS = "sms", "رسالة نصية"
        WHATSAPP = "whatsapp", "واتساب"
        PUSH = "push", "إشعار التطبيق"

    class Status(models.TextChoices):
        QUEUED = "queued", "في قائمة الإرسال"
        SENT = "sent", "مرسلة"
        DELIVERED = "delivered", "تم التسليم"
        FAILED = "failed", "فشل الإرسال"
        READ = "read", "مقروءة"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", null=True, blank=True, on_delete=models.PROTECT, related_name="notifications")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="المستلم", on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField("القناة", max_length=12, choices=Channel.choices, default=Channel.IN_APP)
    category = models.CharField("التصنيف", max_length=60, default="general", db_index=True)
    title = models.CharField("العنوان", max_length=250)
    body = models.TextField("محتوى الإشعار")
    action_url = models.CharField("رابط الإجراء", max_length=500, blank=True)
    payload = models.JSONField("بيانات إضافية", default=dict, blank=True)
    status = models.CharField("حالة الإرسال", max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True)
    is_read = models.BooleanField("مقروء", default=False, db_index=True)
    read_at = models.DateTimeField("وقت القراءة", null=True, blank=True)
    sent_at = models.DateTimeField("وقت الإرسال", null=True, blank=True)
    delivered_at = models.DateTimeField("وقت التسليم", null=True, blank=True)
    provider_reference = models.CharField("مرجع المزود", max_length=120, blank=True)
    failure_reason = models.CharField("سبب الفشل", max_length=500, blank=True)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=120, blank=True)

    class Meta:
        verbose_name = "إشعار"
        verbose_name_plural = "الإشعارات"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["idempotency_key"], condition=~Q(idempotency_key=""), name="notifications_idempotency_key_uniq")]
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"]), models.Index(fields=["school", "category", "created_at"])]

    def __str__(self):
        return self.title

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = self.Status.READ
            self.save(update_fields=["is_read", "read_at", "status", "updated_at"])


class NotificationPreference(UUIDTimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="المستخدم", on_delete=models.CASCADE, related_name="notification_preferences")
    school = models.ForeignKey("tenants.School", verbose_name="المدرسة (فارغ = عام)", null=True, blank=True, on_delete=models.CASCADE, related_name="notification_preferences")
    category = models.CharField("التصنيف", max_length=60)
    channel = models.CharField("القناة", max_length=12, choices=Notification.Channel.choices)
    is_enabled = models.BooleanField("مفعل", default=True)

    class Meta:
        verbose_name = "تفضيل إشعار"
        verbose_name_plural = "تفضيلات الإشعارات"
        constraints = [
            models.UniqueConstraint(fields=["user", "school", "category", "channel"], condition=Q(school__isnull=False), name="notifications_pref_school_uniq"),
            models.UniqueConstraint(fields=["user", "category", "channel"], condition=Q(school__isnull=True), name="notifications_pref_global_uniq"),
        ]

    def __str__(self):
        return f"{self.user} - {self.category} - {self.channel}"


class OutboxEvent(UUIDTimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "بانتظار المعالجة"
        PROCESSING = "processing", "قيد المعالجة"
        PROCESSED = "processed", "تمت المعالجة"
        FAILED = "failed", "فشلت"

    school = models.ForeignKey("tenants.School", verbose_name="المدرسة", null=True, blank=True, on_delete=models.PROTECT, related_name="outbox_events")
    event_name = models.CharField("اسم الحدث", max_length=120, db_index=True)
    aggregate_type = models.CharField("نوع الكيان", max_length=120)
    aggregate_id = models.CharField("معرف الكيان", max_length=64)
    payload = models.JSONField("حمولة الحدث", default=dict)
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=150, unique=True)
    available_at = models.DateTimeField("متاح للمعالجة في", default=timezone.now, db_index=True)
    attempts = models.PositiveSmallIntegerField("عدد المحاولات", default=0)
    max_attempts = models.PositiveSmallIntegerField("الحد الأقصى للمحاولات", default=8)
    last_error = models.TextField("آخر خطأ", blank=True)
    processed_at = models.DateTimeField("وقت المعالجة", null=True, blank=True)

    class Meta:
        verbose_name = "حدث قائمة المعالجة"
        verbose_name_plural = "قائمة الأحداث (Outbox)"
        ordering = ["available_at", "created_at"]
        indexes = [models.Index(fields=["status", "available_at"]), models.Index(fields=["school", "created_at"])]

    def __str__(self):
        return f"{self.event_name} - {self.status}"
