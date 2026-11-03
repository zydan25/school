"""In-app messages, transactional outbox, and WhatsApp/SMS gateway integrations."""
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import UUIDTimestampedModel, TenantOwnedModel
from apps.core.fields import EncryptedTextField


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
        CANCELLED = "cancelled", "ملغاة"

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
        CANCELLED = "cancelled", "ملغاة"

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
    locked_at = models.DateTimeField("وقت قفل العامل", null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "حدث قائمة المعالجة"
        verbose_name_plural = "قائمة الأحداث (Outbox)"
        ordering = ["available_at", "created_at"]
        indexes = [models.Index(fields=["status", "available_at"]), models.Index(fields=["school", "created_at"])]

    def __str__(self):
        return f"{self.event_name} - {self.status}"



class NotificationDeliveryAttempt(UUIDTimestampedModel):
    """محاولة تسليم واحدة، دون تخزين نص الرسالة أو بيانات الاعتماد في سجل المزود."""

    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "قبلها المزود"
        FAILED = "failed", "فشلت المحاولة"

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="delivery_attempts",
        verbose_name="الإشعار",
    )
    attempt_number = models.PositiveSmallIntegerField("رقم المحاولة")
    destination_fingerprint = models.CharField("بصمة الوجهة", max_length=64, blank=True)
    provider = models.CharField("المزود", max_length=40, blank=True)
    status = models.CharField("الحالة", max_length=12, choices=Status.choices)
    provider_reference = models.CharField("مرجع المزود", max_length=160, blank=True)
    response_code = models.PositiveSmallIntegerField("رمز استجابة HTTP", null=True, blank=True)
    error_code = models.CharField("رمز الخطأ", max_length=80, blank=True)
    error_message = models.CharField("وصف الخطأ", max_length=500, blank=True)
    attempted_at = models.DateTimeField("وقت المحاولة", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "محاولة تسليم إشعار"
        verbose_name_plural = "محاولات تسليم الإشعارات"
        ordering = ["-attempted_at"]
        indexes = [models.Index(fields=["notification", "attempted_at"], name="ntf_attempt_notif_time")]

    def __str__(self):
        return f"{self.notification_id} / {self.attempt_number} / {self.status}"


class NotificationDeliveryReceipt(UUIDTimestampedModel):
    """Signed provider delivery/read/failure callback retained for audit."""

    class Status(models.TextChoices):
        SENT = "sent", "قبل المزود الإرسال"
        DELIVERED = "delivered", "تم التسليم"
        READ = "read", "قرأ المستلم الرسالة"
        FAILED = "failed", "فشل التسليم"

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="delivery_receipts",
        verbose_name="الإشعار",
    )
    provider = models.CharField("المزود", max_length=40)
    provider_reference = models.CharField("مرجع المزود", max_length=160)
    status = models.CharField("حالة التسليم", max_length=12, choices=Status.choices)
    error_code = models.CharField("رمز فشل المزود", max_length=80, blank=True)
    received_at = models.DateTimeField("وقت استلام الإيصال", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "إيصال تسليم إشعار"
        verbose_name_plural = "إيصالات تسليم الإشعارات"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "provider_reference", "status"],
                name="ntf_receipt_status_uniq",
            )
        ]
        indexes = [models.Index(fields=["provider_reference", "received_at"], name="ntf_receipt_provider_ref")]


# -----------------------------------------------------------------------------
# WhatsApp & SMS Gateway Integrations per School (ربط بوابات الرسائل والواتساب)
# -----------------------------------------------------------------------------

class SchoolMessagingGateway(UUIDTimestampedModel):
    """إعدادات وتكامل بوابة الرسائل والواتساب لكل مدرسة أو مركزياً للمنصة."""
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "واتساب للأعمال (WhatsApp)"
        SMS = "sms", "رسائل نصية قصيرة (SMS)"
        PUSH = "push", "إشعارات Push"

    class Provider(models.TextChoices):
        CUSTOM_WEBHOOK = "custom_webhook", "رابط ويب هوك مخصص (Custom API)"
        ULTRAMSG = "ultramsg", "UltraMsg WhatsApp API"
        TWILIO = "twilio", "Twilio"
        INFOBIP = "infobip", "Infobip"
        LOCAL_GATEWAY = "local_gateway", "بوابة محلية (Local Gateway)"
        GENERIC_HTTP = "generic_http", "بوابة HTTP موحدة"

    school = models.ForeignKey(
        "tenants.School",
        verbose_name="المدرسة (فارغ = بوابة المنصة العامة)",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="messaging_gateways",
    )
    name = models.CharField("اسم البوابة / التوصيف", max_length=150)
    channel = models.CharField("القناة", max_length=12, choices=Channel.choices, default=Channel.WHATSAPP)
    provider = models.CharField("المزود التقني", max_length=20, choices=Provider.choices, default=Provider.CUSTOM_WEBHOOK)
    
    # Endpoint & Authentication
    api_endpoint_url = models.URLField("رابط واجهة الإرسال (API Endpoint URL)", max_length=500)
    auth_token = EncryptedTextField("مفتاح المصادقة والتوكن (API Key / Token)", blank=True)
    sender_id = models.CharField("معرف المرسل أو رقم الهاتف (Instance ID / Sender Phone)", max_length=100, blank=True)
    webhook_verify_token = EncryptedTextField("المفتاح السري للتحقق من الرسائل الواردة (Webhook Secret)", blank=True)
    
    # AI Auto-Reply Behavior
    auto_ai_reply = models.BooleanField(
        "تفعيل الرد الآلي الذكي (AI Auto-Responder)",
        default=False,
        help_text="يظل الرد الآلي معطلاً افتراضياً لحماية بيانات الطلاب، ولا يفعل إلا بقرار صريح من المدرسة.",
    )
    
    # Templates & Headers
    custom_headers = models.JSONField("ترويسات HTTP إضافية (Custom Headers)", default=dict, blank=True)
    custom_payload_template = models.JSONField(
        "شكل حمولة البيانات المتوقع (JSON Payload Template)",
        default=dict,
        blank=True,
        help_text="مثال: {'to': '{phone}', 'body': '{message}'}",
    )
    is_active = models.BooleanField("بوابة نشطة ومفعلة", default=True)
    rate_limit_per_minute = models.PositiveSmallIntegerField("حد الإرسال في الدقيقة", default=60)
    rate_limit_window_started_at = models.DateTimeField("بداية نافذة الإرسال", null=True, blank=True)
    rate_limit_window_count = models.PositiveIntegerField("عدد الرسائل في النافذة", default=0)

    class Meta:
        verbose_name = "بوابة ربط رسائل / واتساب"
        verbose_name_plural = "بوابات ربط الرسائل والواتساب"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "channel", "name"],
                condition=Q(school__isnull=False),
                name="notifications_gateway_school_uniq",
            )
        ]

    def __str__(self):
        owner = self.school.name if self.school else "المنصة المركزية"
        return f"{self.name} ({self.get_channel_display()}) - {owner}"


class InboundWebhookMessage(UUIDTimestampedModel):
    """سجل وتوثيق دائم للرسائل الواردة عبر Webhook لمنع التكرار وضمان عدم المعالجة المزدوجة."""
    school = models.ForeignKey(
        "tenants.School",
        verbose_name="المدرسة",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="inbound_webhook_messages",
    )
    provider_msg_id = models.CharField("معرف الرسالة من المزود", max_length=255, db_index=True)
    sender_phone = models.CharField("رقم المرسل", max_length=50)
    received_at = models.DateTimeField("تاريخ ووقت الاستقبال", default=timezone.now)
    processed = models.BooleanField("تمت المعالجة", default=False)
    last_error = models.CharField("آخر خطأ معالجة", max_length=500, blank=True)

    class Meta:
        verbose_name = "رسالة ويب هوك واردة"
        verbose_name_plural = "سجل رسائل الويب هوك الواردة"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "provider_msg_id"],
                name="notifications_inbound_msg_school_uniq",
            )
        ]

    def __str__(self):
        return f"{self.sender_phone}: {self.provider_msg_id}"


def conversation_attachment_path(instance, filename):
    extension = os.path.splitext(os.path.basename(filename))[1].lower()[:12]
    return (
        f"private/schools/{instance.school_id}/conversations/"
        f"{instance.conversation_id}/{uuid.uuid4().hex}{extension}"
    )


class PushDevice(UUIDTimestampedModel):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المستخدم",
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    device_id = models.CharField("معرف الجهاز داخل التطبيق", max_length=160)
    platform = models.CharField("المنصة", max_length=12, choices=Platform.choices)
    push_token = models.CharField("رمز الإشعارات من المزود", max_length=2048, unique=True)
    app_version = models.CharField("إصدار التطبيق", max_length=40, blank=True)
    device_name = models.CharField("اسم الجهاز", max_length=120, blank=True)
    is_active = models.BooleanField("نشط", default=True, db_index=True)
    last_seen_at = models.DateTimeField("آخر نشاط", default=timezone.now)

    class Meta:
        verbose_name = "جهاز إشعارات"
        verbose_name_plural = "أجهزة الإشعارات"
        constraints = [
            models.UniqueConstraint(fields=["user", "device_id"], name="notifications_push_device_user_device_uniq"),
        ]
        indexes = [models.Index(fields=["user", "is_active"], name="ntf_pd_user_active")]

    def __str__(self):
        return f"{self.user} / {self.platform} / {self.device_id}"


class SchoolConversation(TenantOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", "مفتوحة"
        CLOSED = "closed", "مغلقة"

    class ConversationType(models.TextChoices):
        GENERAL = "general", "محادثة عامة"
        STUDENT = "student", "مرتبطة بطالب"
        ADMINISTRATIVE = "administrative", "إدارية"

    subject = models.CharField("موضوع المحادثة", max_length=200)
    conversation_type = models.CharField(
        "نوع المحادثة", max_length=20, choices=ConversationType.choices,
        default=ConversationType.GENERAL,
    )
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT,
        related_name="conversations", verbose_name="الطالب المرتبط",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_school_conversations", verbose_name="أنشأها",
    )
    status = models.CharField("الحالة", max_length=12, choices=Status.choices, default=Status.OPEN)
    last_message_at = models.DateTimeField("آخر رسالة", null=True, blank=True)

    class Meta:
        verbose_name = "محادثة مدرسية"
        verbose_name_plural = "المحادثات المدرسية"
        ordering = ["-last_message_at", "-created_at"]
        indexes = [models.Index(fields=["school", "status", "last_message_at"], name="ntf_sc_school_status")]

    def __str__(self):
        return f"{self.subject} - {self.school}"


class ConversationParticipant(TenantOwnedModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "إدارة المدرسة"
        TEACHER = "teacher", "معلم"
        GUARDIAN = "guardian", "ولي أمر"
        STUDENT = "student", "طالب"
        STAFF = "staff", "موظف"

    conversation = models.ForeignKey(
        SchoolConversation, on_delete=models.CASCADE, related_name="participants",
        verbose_name="المحادثة",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="school_conversation_participations", verbose_name="المشارك",
    )
    role = models.CharField("صفة المشارك", max_length=16, choices=Role.choices)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="added_conversation_participants", verbose_name="أضيف بواسطة",
    )
    is_active = models.BooleanField("مشارك نشط", default=True)
    is_muted = models.BooleanField("كتم الإشعارات", default=False)
    last_read_at = models.DateTimeField("آخر قراءة", null=True, blank=True)

    class Meta:
        verbose_name = "مشارك محادثة"
        verbose_name_plural = "مشاركو المحادثات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "conversation", "user"],
                condition=models.Q(is_archived=False),
                name="notifications_conversation_participant_uniq",
            ),
        ]
        indexes = [models.Index(fields=["school", "user", "is_active"], name="ntf_cp_user_active")]

    def clean(self):
        super().clean()
        if self.conversation_id and self.conversation.school_id != self.school_id:
            from django.core.exceptions import ValidationError
            raise ValidationError({"conversation": "المحادثة لا تتبع المدرسة نفسها."})

    def __str__(self):
        return f"{self.user} / {self.conversation}"


class ConversationMessage(TenantOwnedModel):
    class MessageType(models.TextChoices):
        TEXT = "text", "نص"
        FILE = "file", "مرفق"
        SYSTEM = "system", "نظام"

    conversation = models.ForeignKey(
        SchoolConversation, on_delete=models.CASCADE, related_name="messages",
        verbose_name="المحادثة",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="school_conversation_messages", verbose_name="المرسل",
    )
    message_type = models.CharField("نوع الرسالة", max_length=12, choices=MessageType.choices, default=MessageType.TEXT)
    body = models.TextField("محتوى الرسالة", blank=True)
    attachment = models.FileField("المرفق الخاص", upload_to=conversation_attachment_path, storage=__import__("apps.core.storage", fromlist=["private_storage"]).private_storage, blank=True)
    attachment_name = models.CharField("اسم الملف الأصلي", max_length=255, blank=True)
    attachment_size = models.PositiveBigIntegerField("حجم المرفق", default=0)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="replies", verbose_name="رد على رسالة",
    )
    edited_at = models.DateTimeField("تاريخ التعديل", null=True, blank=True)
    is_deleted = models.BooleanField("محذوفة من العرض", default=False)

    class Meta:
        verbose_name = "رسالة محادثة"
        verbose_name_plural = "رسائل المحادثات"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["school", "conversation", "created_at"], name="ntf_cm_conv_time")]

    def clean(self):
        super().clean()
        if self.conversation_id and self.conversation.school_id != self.school_id:
            from django.core.exceptions import ValidationError
            raise ValidationError({"conversation": "المحادثة لا تتبع المدرسة نفسها."})
        if not self.body and not self.attachment:
            from django.core.exceptions import ValidationError
            raise ValidationError("يجب إرسال نص أو ملف مرفق على الأقل.")

    def __str__(self):
        return f"{self.sender or 'النظام'} - {self.created_at}"


class SchoolEmailGateway(UUIDTimestampedModel):
    """SMTP settings and an encrypted password scoped to one school."""

    school = models.OneToOneField(
        "tenants.School", on_delete=models.CASCADE,
        related_name="email_gateway", verbose_name="المدرسة",
    )
    is_active = models.BooleanField("بوابة البريد مفعلة", default=False)
    host = models.CharField("خادم SMTP", max_length=255, blank=True)
    port = models.PositiveSmallIntegerField("منفذ SMTP", default=587)
    username = models.CharField("اسم مستخدم SMTP", max_length=255, blank=True)
    password = EncryptedTextField("كلمة مرور SMTP", blank=True)
    from_email = models.EmailField("عنوان المرسل", blank=True)
    use_tls = models.BooleanField("TLS", default=True)
    use_ssl = models.BooleanField("SSL", default=False)
    rate_limit_per_minute = models.PositiveSmallIntegerField("حد الإرسال في الدقيقة", default=60)
    rate_limit_window_started_at = models.DateTimeField("بداية نافذة الإرسال", null=True, blank=True)
    rate_limit_window_count = models.PositiveIntegerField("عدد الرسائل في النافذة", default=0)

    class Meta:
        verbose_name = "بوابة البريد الإلكتروني للمدرسة"
        verbose_name_plural = "بوابات البريد الإلكتروني للمدارس"

    def clean(self):
        super().clean()
        if self.use_tls and self.use_ssl:
            raise ValidationError("اختر TLS أو SSL، ولا يمكن تفعيلهما معاً.")
        if self.is_active and (not self.host or not self.from_email):
            raise ValidationError("يجب تحديد خادم SMTP وعنوان المرسل قبل التفعيل.")
        if self.port < 1 or self.port > 65535:
            raise ValidationError({"port": "منفذ SMTP غير صالح."})

    def __str__(self):
        return f"{self.school} / SMTP"
