"""Resolve a requested school only after checking the authenticated user's access."""
from django.db.models import Q
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class SchoolContextMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.school = None
        request.school_membership = None
        request.school_context_error = None
        user = getattr(request, "user", None)

        # Resolve the same credentials as DRF, including per-device sessions.
        if not user or not user.is_authenticated:
            auth_parts = request.headers.get("Authorization", "").strip().split()
            if len(auth_parts) == 2 and auth_parts[0].lower() in {"token", "bearer"}:
                from apps.accounts.session_services import authenticate_api_credential
                authenticated = authenticate_api_credential(auth_parts[1])
                if authenticated is not None:
                    user, _auth_object = authenticated
                    request.user = user

        if not user or not user.is_authenticated:
            return None

        from apps.accounts.models import SchoolMembership
        from apps.accounts.services import is_platform_operator
        from apps.tenants.models import School

        platform_operator = is_platform_operator(user)
        requested_code = (request.headers.get("X-School-Code") or "").strip().upper()
        requested_id = (request.headers.get("X-School-ID") or "").strip() or request.session.get("active_school_id")
        membership_qs = SchoolMembership.objects.filter(
            user=user, status=SchoolMembership.Status.ACTIVE,
            school__status=School.Status.ACTIVE,
            school__is_archived=False,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).select_related("school")

        if requested_code:
            membership = membership_qs.filter(school__code=requested_code).first()
            if membership:
                request.school = membership.school
                request.school_membership = membership
                return None
            if platform_operator:
                request.school = School.objects.filter(
                    code=requested_code, status=School.Status.ACTIVE,
                    is_archived=False,
                ).first()
                return None
            request.school_context_error = "لا تملك عضوية نشطة في المدرسة المطلوبة."
            return None

        if requested_id:
            membership = membership_qs.filter(school_id=requested_id).first()
            if membership:
                request.school = membership.school
                request.school_membership = membership
                return None
            if platform_operator:
                request.school = School.objects.filter(
                    pk=requested_id, status=School.Status.ACTIVE,
                    is_archived=False,
                ).first()
                return None
            request.school_context_error = "المدرسة المختارة غير متاحة لهذا الحساب."
            return None

        membership = membership_qs.filter(is_default=True).first()
        if membership is None and membership_qs.count() == 1:
            membership = membership_qs.first()
        if membership:
            request.school = membership.school
            request.school_membership = membership
        elif membership_qs.exists():
            request.school_context_error = "لديك أكثر من مدرسة؛ أرسل X-School-ID أو X-School-Code لتحديد المدرسة النشطة."
        return None
