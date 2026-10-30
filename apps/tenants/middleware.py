"""Resolve a requested school only after checking the authenticated user's access."""
from django.utils.deprecation import MiddlewareMixin
from django.db.models import Q
from django.utils import timezone


class SchoolContextMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.school = None
        request.school_membership = None
        request.school_context_error = None
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        from apps.accounts.models import SchoolMembership
        from apps.accounts.services import is_platform_operator
        from apps.tenants.models import School

        platform_operator = is_platform_operator(user)
        requested_code = (request.headers.get("X-School-Code") or "").strip().upper()
        requested_id = request.session.get("active_school_id")
        membership_qs = SchoolMembership.objects.filter(
            user=user, status=SchoolMembership.Status.ACTIVE,
            school__status=School.Status.ACTIVE,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).select_related("school")

        if requested_code:
            membership = membership_qs.filter(school__code=requested_code).first()
            if membership:
                request.school = membership.school
                request.school_membership = membership
                return None
            if platform_operator:
                request.school = School.objects.filter(code=requested_code, status=School.Status.ACTIVE).first()
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
                request.school = School.objects.filter(pk=requested_id, status=School.Status.ACTIVE).first()
                return None
            request.school_context_error = "المدرسة المختارة غير متاحة لهذا الحساب."
            return None

        membership = membership_qs.filter(is_default=True).first() or membership_qs.order_by("joined_at", "created_at").first()
        if membership:
            request.school = membership.school
            request.school_membership = membership
        return None
