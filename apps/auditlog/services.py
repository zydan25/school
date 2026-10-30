from django.utils import timezone

from apps.auditlog.models import AuditEvent


def record_event(*, action: str, description: str, actor=None, school=None, obj=None,
                 severity=AuditEvent.Severity.INFO, metadata=None, request=None):
    ip_address = None
    user_agent = ""
    request_id = ""
    if request is not None:
        # REMOTE_ADDR is the direct peer. Do not trust client-controlled X-Forwarded-For here.
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        request_id = getattr(request, "request_id", "")
    return AuditEvent.objects.create(
        school=school, actor=actor, action=action,
        object_type=obj._meta.label if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        description=description[:500], severity=severity,
        metadata=metadata or {}, request_id=request_id,
        ip_address=ip_address, user_agent=user_agent,
        occurred_at=timezone.now(),
    )
