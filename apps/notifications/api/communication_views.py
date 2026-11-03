"""School-scoped communication, preferences, push-device and private attachment APIs."""
from __future__ import annotations

import os

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import has_school_roles, resolve_active_school
from apps.accounts.models import SchoolMembership
from apps.notifications.models import (
    ConversationMessage,
    ConversationParticipant,
    Notification,
    NotificationPreference,
    PushDevice,
    SchoolConversation,
)
from apps.notifications.services import enqueue_notification
from apps.staff.models import StaffMember, Teacher, TeacherAssignment
from apps.students.models import Guardian, Student
from apps.tenants.models import School


ADMIN_ROLES = {
    "admin", "school-admin", "school_admin", "school-director", "school_director",
    "principal", "school-principal", "student-affairs", "student_affairs",
}
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt",
    ".doc", ".docx", ".xls", ".xlsx", ".csv",
}


def _school_context(request):
    school = resolve_active_school(request)
    if school is not None:
        return school
    if getattr(request, "school_context_error", None):
        raise PermissionDenied("سياق المدرسة غير صالح أو أن عضويتك غير نشطة.")

    school_id = request.headers.get("X-School-ID") or request.query_params.get("school_id")
    school_code = request.headers.get("X-School-Code") or request.query_params.get("school_code")
    if not school_id and not school_code:
        raise PermissionDenied("حدد المدرسة النشطة باستخدام X-School-ID أو X-School-Code.")

    qs = School.objects.filter(status=School.Status.ACTIVE, is_archived=False)
    school = qs.filter(pk=school_id).first() if school_id else qs.filter(code=school_code.strip().upper()).first()
    if school is None or not _user_linked_to_school(request.user, school):
        raise PermissionDenied("لا تملك علاقة نشطة بالمدرسة المحددة.")
    return school


def _user_linked_to_school(user, school):
    now = timezone.now()
    membership = SchoolMembership.objects.filter(
        user=user, school=school, status=SchoolMembership.Status.ACTIVE,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).exists()
    return (
        membership
        or school.owner_id == user.pk
        or Student.objects.filter(user=user, school=school, is_archived=False).exists()
        or Guardian.objects.filter(user=user, school=school, is_archived=False).exists()
        or Teacher.objects.filter(user=user, school=school, is_archived=False, is_active_teaching=True).exists()
        or StaffMember.objects.filter(user=user, school=school, is_archived=False, is_active=True).exists()
        or ConversationParticipant.objects.filter(
            user=user, school=school, is_active=True, is_archived=False,
        ).exists()
    )


def _user_role(user, school):
    if school.owner_id == user.pk or has_school_roles(user, school, ADMIN_ROLES):
        return ConversationParticipant.Role.ADMIN
    if Teacher.objects.filter(user=user, school=school, is_archived=False, is_active_teaching=True).exists():
        return ConversationParticipant.Role.TEACHER
    if Guardian.objects.filter(user=user, school=school, is_archived=False).exists():
        return ConversationParticipant.Role.GUARDIAN
    if Student.objects.filter(user=user, school=school, is_archived=False).exists():
        return ConversationParticipant.Role.STUDENT
    if StaffMember.objects.filter(user=user, school=school, is_archived=False, is_active=True).exists():
        return ConversationParticipant.Role.STAFF
    membership = SchoolMembership.objects.filter(
        user=user, school=school, status=SchoolMembership.Status.ACTIVE,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()
    if membership:
        roles = membership.get_role_codes()
        if roles & ADMIN_ROLES:
            return ConversationParticipant.Role.ADMIN
        if "teacher" in roles:
            return ConversationParticipant.Role.TEACHER
        if "guardian" in roles:
            return ConversationParticipant.Role.GUARDIAN
        if "student" in roles:
            return ConversationParticipant.Role.STUDENT
        return ConversationParticipant.Role.STAFF
    return None


def _can_access_student(user, school, student):
    if student.school_id != school.pk or student.is_archived:
        return False
    if school.owner_id == user.pk or has_school_roles(user, school, ADMIN_ROLES):
        return True
    if student.user_id == user.pk:
        return True
    guardian = Guardian.objects.filter(user=user, school=school, is_archived=False).first()
    if guardian and guardian.children.filter(pk=student.pk, is_archived=False).exists():
        return True
    teacher = Teacher.objects.filter(user=user, school=school, is_archived=False, is_active_teaching=True).first()
    return bool(
        teacher and student.section_id and TeacherAssignment.objects.filter(
            school=school, teacher=teacher, section_id=student.section_id,
            is_archived=False, academic_year__status="active",
        ).exists()
    )


def _conversation_for_participant(request, school, conversation_id):
    participant = ConversationParticipant.objects.select_related("conversation").filter(
        conversation_id=conversation_id,
        school=school,
        user=request.user,
        is_active=True,
        is_archived=False,
        conversation__school=school,
        conversation__is_archived=False,
    ).first()
    if participant is None:
        raise NotFound("المحادثة غير موجودة أو أنك لست مشاركاً نشطاً فيها.")
    return participant.conversation, participant


def _conversation_payload(conversation, participant):
    unread_qs = conversation.messages.filter(
        is_archived=False, is_deleted=False,
    ).exclude(sender_id=participant.user_id)
    if participant.last_read_at:
        unread_qs = unread_qs.filter(created_at__gt=participant.last_read_at)
    unread = unread_qs.count()
    return {
        "id": str(conversation.pk),
        "subject": conversation.subject,
        "type": conversation.conversation_type,
        "student_id": str(conversation.student_id) if conversation.student_id else None,
        "status": conversation.status,
        "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        "unread_count": unread,
        "created_at": conversation.created_at.isoformat(),
    }


class NotificationPreferencesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = _school_context(request)
        preferences = NotificationPreference.objects.filter(
            user=request.user, school=school,
        ).order_by("category", "channel")
        return Response({"preferences": [
            {"category": item.category, "channel": item.channel, "is_enabled": item.is_enabled}
            for item in preferences
        ]})

    def post(self, request):
        school = _school_context(request)
        category = str(request.data.get("category", "")).strip()
        channel = str(request.data.get("channel", "")).strip()
        enabled = request.data.get("is_enabled")
        valid_channels = {choice[0] for choice in Notification.Channel.choices if choice[0] != Notification.Channel.IN_APP}
        if not category or len(category) > 60 or channel not in valid_channels or not isinstance(enabled, bool):
            raise ValidationError("أرسل تصنيفاً صالحاً وقناة خارجية وحالة is_enabled منطقية.")
        preference, _ = NotificationPreference.objects.update_or_create(
            user=request.user, school=school, category=category, channel=channel,
            defaults={"is_enabled": enabled},
        )
        return Response({
            "category": preference.category, "channel": preference.channel,
            "is_enabled": preference.is_enabled,
        })


class PushDevicesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = PushDevice.objects.filter(user=request.user, is_active=True).order_by("-last_seen_at")
        return Response({"devices": [
            {
                "device_id": item.device_id, "platform": item.platform,
                "device_name": item.device_name, "app_version": item.app_version,
                "token_suffix": item.push_token[-8:], "last_seen_at": item.last_seen_at.isoformat(),
            } for item in devices
        ]})

    def post(self, request):
        device_id = str(request.data.get("device_id", "")).strip()
        platform = str(request.data.get("platform", "")).strip()
        token = str(request.data.get("push_token", "")).strip()
        if not device_id or len(device_id) > 160 or platform not in PushDevice.Platform.values or not token or len(token) > 2048:
            raise ValidationError("بيانات الجهاز أو رمز Push غير صالحة.")
        try:
            device, _ = PushDevice.objects.update_or_create(
                user=request.user, device_id=device_id,
                defaults={
                    "platform": platform, "push_token": token,
                    "device_name": str(request.data.get("device_name", ""))[:120],
                    "app_version": str(request.data.get("app_version", ""))[:40],
                    "is_active": True, "last_seen_at": timezone.now(),
                },
            )
        except IntegrityError as exc:
            raise ValidationError("رمز Push مسجل مسبقاً على حساب آخر.") from exc
        return Response({"device_id": device.device_id, "platform": device.platform, "is_active": True}, status=status.HTTP_200_OK)

    def delete(self, request):
        device_id = str(request.query_params.get("device_id", "")).strip()
        if not device_id:
            raise ValidationError("معرف الجهاز مطلوب.")
        updated = PushDevice.objects.filter(user=request.user, device_id=device_id, is_active=True).update(
            is_active=False, updated_at=timezone.now(),
        )
        if not updated:
            raise NotFound("الجهاز غير موجود.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class SchoolConversationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = _school_context(request)
        participation = ConversationParticipant.objects.filter(
            school=school, user=request.user, is_active=True, is_archived=False,
            conversation__school=school, conversation__is_archived=False,
        ).select_related("conversation").order_by("-conversation__last_message_at", "-conversation__created_at")
        return Response({"conversations": [
            _conversation_payload(item.conversation, item) for item in participation[:100]
        ]})

    @transaction.atomic
    def post(self, request):
        school = _school_context(request)
        if not _user_linked_to_school(request.user, school):
            raise PermissionDenied("لا يمكن إنشاء محادثة خارج نطاق مدرستك.")
        subject = str(request.data.get("subject", "")).strip()
        conversation_type = str(request.data.get("type", SchoolConversation.ConversationType.GENERAL))
        if not subject or len(subject) > 200 or conversation_type not in SchoolConversation.ConversationType.values:
            raise ValidationError("موضوع المحادثة أو نوعها غير صالح.")
        student = None
        student_id = request.data.get("student_id")
        if conversation_type == SchoolConversation.ConversationType.STUDENT:
            if not student_id:
                raise ValidationError({"student_id": "المحادثة المرتبطة بطالب تتطلب student_id."})
            student = Student.objects.filter(pk=student_id, school=school, is_archived=False).first()
            if student is None or not _can_access_student(request.user, school, student):
                raise PermissionDenied("لا تملك علاقة مخولة بالطالب المحدد.")
        elif student_id:
            raise ValidationError({"student_id": "لا ترسل student_id إلا للمحادثة المرتبطة بطالب."})

        caller_role = _user_role(request.user, school)
        if caller_role is None:
            raise PermissionDenied("لا يوجد ملف أو عضوية نشطة تربطك بالمدرسة.")
        conversation = SchoolConversation.objects.create(
            school=school, subject=subject, conversation_type=conversation_type,
            student=student, created_by=request.user,
        )
        ConversationParticipant.objects.create(
            school=school, conversation=conversation, user=request.user,
            role=caller_role, added_by=request.user,
        )
        participant_ids = request.data.get("participant_ids", [])
        if not isinstance(participant_ids, list) or len(participant_ids) > 30:
            raise ValidationError({"participant_ids": "قائمة المشاركين غير صالحة أو تتجاوز 30 مشاركاً."})
        for user_id in set(str(value) for value in participant_ids):
            user = _school_user(school, user_id)
            role = _user_role(user, school)
            if role is None:
                raise ValidationError("أحد المشاركين لا يملك ملفاً أو عضوية نشطة في المدرسة.")
            if conversation_type == SchoolConversation.ConversationType.STUDENT and role != ConversationParticipant.Role.ADMIN and not _can_access_student(user, school, student):
                raise PermissionDenied("أحد المشاركين غير مرتبط بالطالب المحدد.")
            ConversationParticipant.objects.get_or_create(
                school=school, conversation=conversation, user=user,
                defaults={"role": role, "added_by": request.user, "is_active": True},
            )
        return Response({"conversation": _conversation_payload(
            conversation, conversation.participants.get(user=request.user),
        )}, status=status.HTTP_201_CREATED)


def _school_user(school, user_id):
    from apps.accounts.models import User
    user = User.objects.filter(pk=user_id, is_active=True, status=User.Status.ACTIVE).first()
    if user is None or not _user_linked_to_school(user, school):
        raise ValidationError("المشارك المحدد غير مرتبط بالمدرسة أو حسابه غير نشط.")
    return user


class ConversationMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        school = _school_context(request)
        conversation, participant = _conversation_for_participant(request, school, conversation_id)
        messages = conversation.messages.filter(
            school=school, is_archived=False, is_deleted=False,
        ).select_related("sender", "reply_to").order_by("created_at")
        participant.last_read_at = timezone.now()
        participant.save(update_fields=["last_read_at", "updated_at"])
        return Response({"messages": [
            {
                "id": str(item.pk),
                "sender_id": str(item.sender_id) if item.sender_id else None,
                "sender_name": item.sender.get_full_name() if item.sender else "النظام",
                "type": item.message_type,
                "body": item.body,
                "attachment_name": item.attachment_name,
                "attachment_url": f"/api/v1/notifications/conversations/{conversation.pk}/messages/{item.pk}/attachment/" if item.attachment else None,
                "reply_to_id": str(item.reply_to_id) if item.reply_to_id else None,
                "created_at": item.created_at.isoformat(),
                "edited_at": item.edited_at.isoformat() if item.edited_at else None,
            } for item in messages[:200]
        ], "last_read_at": participant.last_read_at.isoformat()})

    @transaction.atomic
    def post(self, request, conversation_id):
        school = _school_context(request)
        conversation, participant = _conversation_for_participant(request, school, conversation_id)
        if conversation.status != SchoolConversation.Status.OPEN:
            raise PermissionDenied("المحادثة مغلقة ولا تقبل رسائل جديدة.")
        body = str(request.data.get("body", "")).strip()
        attachment = request.FILES.get("attachment")
        if not body and not attachment:
            raise ValidationError("أدخل نصاً أو أرفق ملفاً.")
        if len(body) > 20000:
            raise ValidationError({"body": "نص الرسالة يتجاوز 20000 حرف."})
        if attachment:
            extension = os.path.splitext(attachment.name)[1].lower()
            if attachment.size > MAX_ATTACHMENT_SIZE or extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
                raise ValidationError("المرفق يتجاوز 10 ميغابايت أو أن نوع ملفه غير مسموح.")
        reply_to = None
        reply_to_id = request.data.get("reply_to_id")
        if reply_to_id:
            reply_to = ConversationMessage.objects.filter(
                pk=reply_to_id, conversation=conversation, school=school,
                is_archived=False, is_deleted=False,
            ).first()
            if reply_to is None:
                raise ValidationError({"reply_to_id": "الرسالة الأصلية لا تتبع هذه المحادثة."})
        message = ConversationMessage.objects.create(
            school=school, conversation=conversation, sender=request.user,
            message_type=ConversationMessage.MessageType.FILE if attachment else ConversationMessage.MessageType.TEXT,
            body=body, attachment=attachment, attachment_name=os.path.basename(attachment.name)[:255] if attachment else "",
            attachment_size=attachment.size if attachment else 0, reply_to=reply_to,
        )
        conversation.last_message_at = message.created_at
        conversation.save(update_fields=["last_message_at", "updated_at"])
        recipients = ConversationParticipant.objects.filter(
            conversation=conversation, school=school, is_active=True, is_archived=False,
        ).exclude(user=request.user).select_related("user")
        for target in recipients:
            if target.is_muted:
                continue
            enqueue_notification(
                recipient=target.user, school=school, channel=Notification.Channel.IN_APP,
                category="conversation", title=conversation.subject,
                body=(body[:220] if body else "أرسل مرفقاً في المحادثة."),
                payload={"conversation_id": str(conversation.pk), "message_id": str(message.pk)},
                idempotency_key=f"conversation-message:{message.pk}:{target.user_id}",
            )
        return Response({
            "id": str(message.pk), "type": message.message_type, "body": message.body,
            "attachment_name": message.attachment_name,
            "attachment_url": f"/api/v1/notifications/conversations/{conversation.pk}/messages/{message.pk}/attachment/" if message.attachment else None,
            "created_at": message.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class ConversationParticipantsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        school = _school_context(request)
        conversation, _ = _conversation_for_participant(request, school, conversation_id)
        participants = conversation.participants.filter(
            school=school, is_active=True, is_archived=False,
        ).select_related("user").order_by("created_at")
        return Response({"participants": [
            {"user_id": str(item.user_id), "name": item.user.get_full_name(), "role": item.role,
             "is_muted": item.is_muted,
             "last_read_at": item.last_read_at.isoformat() if item.last_read_at else None}
            for item in participants
        ]})

    @transaction.atomic
    def post(self, request, conversation_id):
        school = _school_context(request)
        conversation, _ = _conversation_for_participant(request, school, conversation_id)
        if conversation.created_by_id != request.user.pk and not (
            school.owner_id == request.user.pk or has_school_roles(request.user, school, ADMIN_ROLES)
        ):
            raise PermissionDenied("إضافة المشاركين تتطلب منشئ المحادثة أو إدارة المدرسة.")
        if conversation.status != SchoolConversation.Status.OPEN:
            raise PermissionDenied("لا يمكن إضافة مشاركين إلى محادثة مغلقة.")
        user = _school_user(school, request.data.get("user_id"))
        role = _user_role(user, school)
        if conversation.student_id and role != ConversationParticipant.Role.ADMIN:
            if not _can_access_student(user, school, conversation.student):
                raise PermissionDenied("المشارك غير مرتبط بالطالب المحدد.")
        participant, created = ConversationParticipant.objects.get_or_create(
            school=school, conversation=conversation, user=user,
            defaults={"role": role, "added_by": request.user, "is_active": True},
        )
        if not created and not participant.is_active:
            participant.is_active = True
            participant.added_by = request.user
            participant.save(update_fields=["is_active", "added_by", "updated_at"])
        return Response({"user_id": str(user.pk), "role": role, "is_active": True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, conversation_id):
        school = _school_context(request)
        conversation, _ = _conversation_for_participant(request, school, conversation_id)
        if conversation.created_by_id != request.user.pk and not (
            school.owner_id == request.user.pk or has_school_roles(request.user, school, ADMIN_ROLES)
        ):
            raise PermissionDenied("إزالة المشاركين تتطلب منشئ المحادثة أو إدارة المدرسة.")
        user_id = str(request.query_params.get("user_id", ""))
        if not user_id or user_id == str(request.user.pk):
            raise ValidationError("حدد مشاركاً آخر لإزالته.")
        updated = ConversationParticipant.objects.filter(
            school=school, conversation=conversation, user_id=user_id,
            is_active=True, is_archived=False,
        ).update(is_active=False, updated_at=timezone.now())
        if not updated:
            raise NotFound("المشارك غير موجود.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        school = _school_context(request)
        conversation, _ = _conversation_for_participant(request, school, conversation_id)
        if conversation.created_by_id != request.user.pk and not (
            school.owner_id == request.user.pk or has_school_roles(request.user, school, ADMIN_ROLES)
        ):
            raise PermissionDenied("تغيير حالة المحادثة يتطلب منشئها أو إدارة المدرسة.")
        requested = request.data.get("status")
        if requested not in SchoolConversation.Status.values:
            raise ValidationError({"status": "الحالة يجب أن تكون open أو closed."})
        conversation.status = requested
        conversation.save(update_fields=["status", "updated_at"])
        return Response({"id": str(conversation.pk), "status": conversation.status})


class ConversationAttachmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id, message_id):
        school = _school_context(request)
        conversation, _ = _conversation_for_participant(request, school, conversation_id)
        message = ConversationMessage.objects.filter(
            pk=message_id, conversation=conversation, school=school,
            is_archived=False, is_deleted=False,
        ).first()
        if message is None or not message.attachment:
            raise Http404
        handle = message.attachment.open("rb")
        response = FileResponse(handle, content_type="application/octet-stream")
        from urllib.parse import quote
        filename = os.path.basename(message.attachment_name or message.attachment.name).replace('"', "")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8\'\'{quote(filename)}"
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
