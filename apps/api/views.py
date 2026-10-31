from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, version):
        return Response({"status": "ok", "service": "school-api", "version": version})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        from apps.api.v1.serializers import UserProfileSerializer

        return Response({
            "user": UserProfileSerializer(
                request.user, context={"request": request},
            ).data,
            "active_school": (
                {
                    "id": str(request.school.pk),
                    "code": request.school.code,
                    "name": request.school.name,
                }
                if request.school else None
            ),
            "is_platform_admin": request.user.is_platform_admin,
        })

    def patch(self, request, version):
        from apps.api.v1.serializers import UserProfileSerializer

        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "user": serializer.data,
            "active_school": (
                {
                    "id": str(request.school.pk),
                    "code": request.school.code,
                    "name": request.school.name,
                }
                if request.school else None
            ),
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


class APILoginView(APIView):
    """تسجيل الدخول لتطبيقات الجوال والأنظمة الخارجية واسترجاع رمز الوصول Token."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        from django.contrib.auth import authenticate
        from rest_framework.authtoken.models import Token

        from apps.accounts.models import SchoolMembership

        phone = (request.data.get("phone") or "").strip()
        password = request.data.get("password") or ""

        if not phone or not password:
            return Response({"error": "يرجى إدخال رقم الهاتف وكلمة المرور."}, status=400)

        user = authenticate(request, username=phone, password=password)
        if not user:
            # Fallback direct lookup by phone if custom backend expects phone parameter
            from apps.accounts.models import User
            usr = User.objects.filter(phone=phone).first()
            if usr and usr.check_password(password):
                user = usr

        if not user or not user.is_active:
            return Response({"error": "بيانات الدخول غير صحيحة أو الحساب غير نشط."}, status=401)

        token, _ = Token.objects.get_or_create(user=user)

        memberships = SchoolMembership.objects.filter(
            user=user,
            status=SchoolMembership.Status.ACTIVE,
            school__status="active",
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).select_related("school")

        schools_data = []
        for m in memberships:
            schools_data.append({
                "school_id": str(m.school_id),
                "school_code": m.school.code,
                "school_name": m.school.name,
                "roles": list(m.get_role_codes()),
                "is_default": m.is_default,
            })

        return Response({
            "token": token.key,
            "user": {
                "id": str(user.pk),
                "phone": user.phone,
                "full_name": user.get_full_name(),
                "email": user.email,
                "is_platform_admin": user.is_platform_admin,
            },
            "schools": schools_data,
        })


class APILogoutView(APIView):
    """تسجيل الخروج وإبطال رمز الوصول Token."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from rest_framework.authtoken.models import Token
        Token.objects.filter(user=request.user).delete()
        return Response({"message": "تم تسجيل الخروج بنجاح وإلغاء صلاحية الجلسة."})
