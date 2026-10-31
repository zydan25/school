# Generated migration for mobile push delivery and school conversations.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models
import apps.notifications.models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_inboundwebhookmessage"),
        ("students", "0004_studentenrollment"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PushDevice",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("device_id", models.CharField(max_length=160, verbose_name="معرف الجهاز داخل التطبيق")),
                ("platform", models.CharField(max_length=12, choices=[("android", "Android"), ("ios", "iOS"), ("web", "Web")], verbose_name="المنصة")),
                ("push_token", models.CharField(max_length=2048, unique=True, verbose_name="رمز الإشعارات من المزود")),
                ("app_version", models.CharField(max_length=40, blank=True, verbose_name="إصدار التطبيق")),
                ("device_name", models.CharField(max_length=120, blank=True, verbose_name="اسم الجهاز")),
                ("is_active", models.BooleanField(default=True, db_index=True, verbose_name="نشط")),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="آخر نشاط")),
                ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="push_devices", verbose_name="المستخدم")),
            ],
            options={
                "verbose_name": "جهاز إشعارات",
                "verbose_name_plural": "أجهزة الإشعارات",
                "indexes": [models.Index(fields=["user", "is_active"], name="notifications_push_user_active_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "device_id"), name="notifications_push_device_user_device_uniq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SchoolConversation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(default=False, db_index=True, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(max_length=500, blank=True, verbose_name="سبب الأرشفة")),
                ("subject", models.CharField(max_length=200, verbose_name="موضوع المحادثة")),
                ("conversation_type", models.CharField(max_length=20, choices=[("general", "محادثة عامة"), ("student", "مرتبطة بطالب"), ("administrative", "إدارية")], default="general", verbose_name="نوع المحادثة")),
                ("status", models.CharField(max_length=12, choices=[("open", "مفتوحة"), ("closed", "مغلقة")], default="open", verbose_name="الحالة")),
                ("last_message_at", models.DateTimeField(null=True, blank=True, verbose_name="آخر رسالة")),
                ("archived_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications_schoolconversation_archived", verbose_name="أرشفه")),
                ("branch", models.ForeignKey(to="tenants.branch", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="notifications_schoolconversation_records", verbose_name="الفرع")),
                ("school", models.ForeignKey(to="tenants.school", on_delete=django.db.models.deletion.PROTECT, related_name="notifications_schoolconversation_records", verbose_name="المدرسة")),
                ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="created_school_conversations", verbose_name="أنشأها")),
                ("student", models.ForeignKey(to="students.student", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversations", verbose_name="الطالب المرتبط")),
            ],
            options={
                "verbose_name": "محادثة مدرسية",
                "verbose_name_plural": "المحادثات المدرسية",
                "ordering": ["-last_message_at", "-created_at"],
                "indexes": [models.Index(fields=["school", "status", "last_message_at"], name="notifications_conv_school_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ConversationParticipant",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(default=False, db_index=True, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(max_length=500, blank=True, verbose_name="سبب الأرشفة")),
                ("role", models.CharField(max_length=16, choices=[("admin", "إدارة المدرسة"), ("teacher", "معلم"), ("guardian", "ولي أمر"), ("student", "طالب"), ("staff", "موظف")], verbose_name="صفة المشارك")),
                ("is_active", models.BooleanField(default=True, verbose_name="مشارك نشط")),
                ("is_muted", models.BooleanField(default=False, verbose_name="كتم الإشعارات")),
                ("last_read_at", models.DateTimeField(null=True, blank=True, verbose_name="آخر قراءة")),
                ("archived_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications_conversationparticipant_archived", verbose_name="أرشفه")),
                ("branch", models.ForeignKey(to="tenants.branch", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="notifications_conversationparticipant_records", verbose_name="الفرع")),
                ("school", models.ForeignKey(to="tenants.school", on_delete=django.db.models.deletion.PROTECT, related_name="notifications_conversationparticipant_records", verbose_name="المدرسة")),
                ("added_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="added_conversation_participants", verbose_name="أضيف بواسطة")),
                ("conversation", models.ForeignKey(to="notifications.schoolconversation", on_delete=django.db.models.deletion.CASCADE, related_name="participants", verbose_name="المحادثة")),
                ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="school_conversation_participations", verbose_name="المشارك")),
            ],
            options={
                "verbose_name": "مشارك محادثة",
                "verbose_name_plural": "مشاركو المحادثات",
                "indexes": [models.Index(fields=["school", "user", "is_active"], name="notifications_conv_user_active_idx")],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(is_archived=False), fields=("school", "conversation", "user"), name="notifications_conversation_participant_uniq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ConversationMessage",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("is_archived", models.BooleanField(default=False, db_index=True, verbose_name="مؤرشف")),
                ("archived_at", models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الأرشفة")),
                ("archive_reason", models.CharField(max_length=500, blank=True, verbose_name="سبب الأرشفة")),
                ("message_type", models.CharField(max_length=12, choices=[("text", "نص"), ("file", "مرفق"), ("system", "نظام")], default="text", verbose_name="نوع الرسالة")),
                ("body", models.TextField(blank=True, verbose_name="محتوى الرسالة")),
                ("attachment", models.FileField(upload_to=apps.notifications.models.conversation_attachment_path, blank=True, verbose_name="المرفق الخاص")),
                ("attachment_name", models.CharField(max_length=255, blank=True, verbose_name="اسم الملف الأصلي")),
                ("attachment_size", models.PositiveBigIntegerField(default=0, verbose_name="حجم المرفق")),
                ("edited_at", models.DateTimeField(null=True, blank=True, verbose_name="تاريخ التعديل")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="محذوفة من العرض")),
                ("archived_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications_conversationmessage_archived", verbose_name="أرشفه")),
                ("branch", models.ForeignKey(to="tenants.branch", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="notifications_conversationmessage_records", verbose_name="الفرع")),
                ("school", models.ForeignKey(to="tenants.school", on_delete=django.db.models.deletion.PROTECT, related_name="notifications_conversationmessage_records", verbose_name="المدرسة")),
                ("conversation", models.ForeignKey(to="notifications.schoolconversation", on_delete=django.db.models.deletion.CASCADE, related_name="messages", verbose_name="المحادثة")),
                ("reply_to", models.ForeignKey(to="notifications.conversationmessage", null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replies", verbose_name="رد على رسالة")),
                ("sender", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="school_conversation_messages", verbose_name="المرسل")),
            ],
            options={
                "verbose_name": "رسالة محادثة",
                "verbose_name_plural": "رسائل المحادثات",
                "ordering": ["created_at"],
                "indexes": [models.Index(fields=["school", "conversation", "created_at"], name="notifications_conv_msg_time_idx")],
            },
        ),
    ]
