from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, version):
        return Response({"status": "ok", "service": "school-api", "version": version})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        return Response({
            "id": str(request.user.pk),
            "full_name": request.user.full_name,
            "phone": request.user.phone,
            "email": request.user.email,
            "is_platform_admin": request.user.is_platform_admin,
            "school": ({"id": str(request.school.pk), "code": request.school.code, "name": request.school.name} if request.school else None),
        })


class AvailableSchoolsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        from apps.accounts.models import SchoolMembership
        from apps.accounts.services import is_platform_operator
        from apps.tenants.models import School
        if is_platform_operator(request.user):
            schools = School.objects.filter(status=School.Status.ACTIVE)
        else:
            memberships = SchoolMembership.objects.filter(
                user=request.user, status=SchoolMembership.Status.ACTIVE,
                school__status=School.Status.ACTIVE,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).select_related("school")
            return Response({"results": [
                {"id": str(item.school_id), "code": item.school.code, "name": item.school.name, "is_default": item.is_default}
                for item in memberships
            ]})
        return Response({"results": [
            {"id": str(item.pk), "code": item.code, "name": item.name, "is_default": False}
            for item in schools
        ]})


class SwitchSchoolContextView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, version):
        from apps.tenants.services import resolve_school_for_user
        code = (request.data.get("school_code") or "").strip()
        if not code:
            return Response({"detail": "أدخل كود المدرسة."}, status=400)
        school = resolve_school_for_user(user=request.user, school_code=code)
        request.session["active_school_id"] = str(school.pk)
        request.session.modified = True
        return Response({"school": {"id": str(school.pk), "code": school.code, "name": school.name}})
