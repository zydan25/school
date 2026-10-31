from django.contrib.auth import password_validation
from django.core.exceptions import ImproperlyConfigured, ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
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

        data = UserProfileSerializer(
            request.user, context={"request": request},
        ).data
        data["is_platform_admin"] = request.user.is_platform_admin
        data["school"] = (
            {
                "id": str(request.school.pk),
                "code": request.school.code,
                "name": request.school.name,
            }
            if request.school else None
        )
        return Response(data)

    def patch(self, request, version):
        from apps.api.v1.serializers import UserProfileSerializer

        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            **UserProfileSerializer(user, context={"request": request}).data,
            "is_platform_admin": user.is_platform_admin,
            "school": (
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
    """Rate-limited phone/password login issuing a separate bearer session per device."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        from datetime import timedelta

        from apps.accounts.models import User
        from apps.accounts.session_services import create_device_session
        from apps.accounts.models import SchoolMembership, normalize_phone

        phone = normalize_phone(request.data.get("phone") or "")
        password = request.data.get("password") or ""
        if not phone or not password:
            return Response(
                {"error": "يرجى إدخال رقم الهاتف وكلمة المرور."},
                status=400,
            )

        now = timezone.now()
        with transaction.atomic():
            user = User.objects.select_for_update().filter(phone=phone).first()
            if user is None:
                return Response({"error": "بيانات الدخول غير صحيحة أو الحساب غير نشط."}, status=401)

            if user.locked_until and user.locked_until > now:
                return Response(
                    {"error": "تم إيقاف محاولات الدخول مؤقتاً؛ حاول بعد انتهاء فترة القفل."},
                    status=423,
                )

            if not user.is_active or user.status != User.Status.ACTIVE:
                return Response({"error": "بيانات الدخول غير صحيحة أو الحساب غير نشط."}, status=401)

            if not user.check_password(password):
                user.failed_login_count += 1
                update_fields = ["failed_login_count", "updated_at"]
                if user.failed_login_count >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                    update_fields.append("locked_until")
                user.save(update_fields=update_fields)
                return Response(
                    {"error": "بيانات الدخول غير صحيحة أو الحساب غير نشط."},
                    status=401,
                )

            user.failed_login_count = 0
            user.locked_until = None
            user.last_seen_at = now
            user.save(update_fields=[
                "failed_login_count", "locked_until", "last_seen_at", "updated_at",
            ])

        device_id = (
            request.headers.get("X-Device-ID")
            or request.data.get("device_id")
            or ""
        )
        device_name = request.data.get("device_name") or request.headers.get("X-Device-Name", "")
        user_agent = request.headers.get("User-Agent", "")
        ip_address = request.META.get("REMOTE_ADDR")
        session, raw_token = create_device_session(
            user=user,
            device_id=device_id,
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        memberships = SchoolMembership.objects.filter(
            user=user,
            status=SchoolMembership.Status.ACTIVE,
            school__status="active",
            school__is_archived=False,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).select_related("school")

        schools_data = [{
            "school_id": str(m.school_id),
            "school_code": m.school.code,
            "school_name": m.school.name,
            "roles": list(m.get_role_codes()),
            "is_default": m.is_default,
        } for m in memberships]

        return Response({
            "token": raw_token,  # Kept for existing mobile clients.
            "access_token": raw_token,
            "token_type": "Bearer",
            "expires_at": session.expires_at.isoformat(),
            "session_id": str(session.pk),
            "device_id": session.device_id,
            "user": {
                "id": str(user.pk),
                "phone": user.phone,
                "full_name": user.get_full_name(),
                "email": user.email,
                "is_platform_admin": user.is_platform_admin,
                "phone_verified": user.phone_verified_at is not None,
            },
            "schools": schools_data,
        })


class PhoneRegistrationAPIView(APIView):
    """Create a pending account and send a one-time phone verification code."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import User, normalize_phone
        from apps.accounts.session_services import issue_phone_challenge

        phone = normalize_phone(request.data.get("phone") or "")
        first_name = (request.data.get("first_name") or "").strip()
        middle_name = (request.data.get("middle_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        password_confirm = request.data.get("password_confirm") or ""

        if not phone or not first_name or not last_name:
            raise ValidationError({"detail": "رقم الهاتف والاسم الأول واسم العائلة مطلوبة."})
        if password != password_confirm:
            raise ValidationError({"password_confirm": "كلمتا المرور غير متطابقتين."})
        candidate = User(
            phone=phone,
            email=email,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
        )
        try:
            password_validation.validate_password(password, user=candidate)
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)}) from exc

        if User.objects.filter(phone=phone).exists():
            raise ValidationError({"phone": "رقم الهاتف مسجل بالفعل."})

        try:
            user = User.objects.create_user(
                phone=phone,
                password=password,
                email=email,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                status=User.Status.PENDING,
                is_active=False,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc

        try:
            issue_phone_challenge(
                user=user,
                purpose="verify_phone",
                request_ip=request.META.get("REMOTE_ADDR"),
            )
        except ImproperlyConfigured as exc:
            return Response(
                {"error": str(exc), "account_status": user.status},
                status=503,
            )
        except Exception as exc:
            if isinstance(exc, DjangoValidationError):
                raise ValidationError(exc.messages) from exc
            return Response(
                {"error": "تعذر إرسال رمز التحقق حالياً؛ يمكنك إعادة طلبه لاحقاً."},
                status=503,
            )

        return Response({
            "message": "تم إنشاء الحساب المبدئي وإرسال رمز التحقق إلى هاتفك.",
            "phone": user.phone,
            "account_status": user.status,
            "expires_in_seconds": 300,
        }, status=202)


class PhoneVerificationAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import PhoneVerificationChallenge, User, normalize_phone
        from apps.accounts.session_services import consume_phone_challenge

        phone = normalize_phone(request.data.get("phone") or "")
        code = str(request.data.get("code") or "").strip()
        user = User.objects.filter(phone=phone).first()
        if user is None or len(code) != 6 or not code.isdigit():
            raise ValidationError("رمز التحقق غير صحيح أو منتهي الصلاحية.")

        try:
            consume_phone_challenge(
                user=user,
                phone=phone,
                purpose=PhoneVerificationChallenge.Purpose.VERIFY_PHONE,
                code=code,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        if user.status == User.Status.SUSPENDED:
            raise ValidationError("الحساب موقوف؛ تواصل مع إدارة المنصة.")
        user.phone_verified_at = timezone.now()
        user.status = User.Status.ACTIVE
        user.is_active = True
        user.failed_login_count = 0
        user.locked_until = None
        user.save(update_fields=[
            "phone_verified_at", "status", "is_active",
            "failed_login_count", "locked_until", "updated_at",
        ])
        return Response({
            "message": "تم توثيق رقم الهاتف وتفعيل الحساب بنجاح.",
            "phone_verified": True,
            "account_status": user.status,
        })


class ResendPhoneVerificationAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import User, normalize_phone
        from apps.accounts.session_services import issue_phone_challenge

        phone = normalize_phone(request.data.get("phone") or "")
        user = User.objects.filter(
            phone=phone, status=User.Status.PENDING, is_active=False,
        ).first()
        if user is None:
            return Response({"message": "إذا كان الحساب بانتظار التفعيل فسيتم إرسال رمز جديد."}, status=202)
        try:
            issue_phone_challenge(
                user=user, purpose="verify_phone",
                request_ip=request.META.get("REMOTE_ADDR"),
            )
        except ImproperlyConfigured as exc:
            return Response({"error": str(exc)}, status=503)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except Exception:
            return Response({"error": "تعذر إرسال رمز التحقق حالياً."}, status=503)
        return Response({"message": "إذا كان الحساب بانتظار التفعيل فسيتم إرسال رمز جديد."}, status=202)


class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import User, normalize_phone
        from apps.accounts.session_services import issue_phone_challenge

        phone = normalize_phone(request.data.get("phone") or "")
        user = User.objects.filter(
            phone=phone, is_active=True, status=User.Status.ACTIVE,
        ).first()
        if user is not None:
            try:
                issue_phone_challenge(
                    user=user, purpose="password_reset",
                    request_ip=request.META.get("REMOTE_ADDR"),
                )
            except ImproperlyConfigured as exc:
                return Response({"error": str(exc)}, status=503)
            except DjangoValidationError as exc:
                raise ValidationError(exc.messages) from exc
            except Exception:
                return Response({"error": "تعذر إرسال رمز الاستعادة حالياً."}, status=503)
        return Response({
            "message": "إذا كان الرقم مرتبطاً بحساب نشط فسيتم إرسال رمز الاستعادة.",
            "expires_in_seconds": 300,
        }, status=202)


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import PhoneVerificationChallenge, User, normalize_phone
        from apps.accounts.session_services import consume_phone_challenge

        phone = normalize_phone(request.data.get("phone") or "")
        code = str(request.data.get("code") or "").strip()
        password = request.data.get("new_password") or ""
        password_confirm = request.data.get("password_confirm") or ""
        user = User.objects.filter(
            phone=phone, is_active=True, status=User.Status.ACTIVE,
        ).first()
        if user is None or len(code) != 6 or not code.isdigit():
            raise ValidationError("رمز الاستعادة غير صحيح أو منتهي الصلاحية.")
        if password != password_confirm:
            raise ValidationError({"password_confirm": "كلمتا المرور غير متطابقتين."})
        try:
            password_validation.validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)}) from exc
        try:
            consume_phone_challenge(
                user=user, phone=phone,
                purpose=PhoneVerificationChallenge.Purpose.PASSWORD_RESET,
                code=code,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        user.set_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        user.save(update_fields=["password", "failed_login_count", "locked_until", "updated_at"])
        user.device_sessions.filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now(), updated_at=timezone.now(),
        )
        from rest_framework.authtoken.models import Token
        Token.objects.filter(user=user).delete()
        return Response({"message": "تم تغيير كلمة المرور وإبطال جميع الجلسات السابقة."})


class PasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from rest_framework.authtoken.models import Token

        current_password = request.data.get("current_password") or ""
        new_password = request.data.get("new_password") or ""
        password_confirm = request.data.get("password_confirm") or ""
        user = request.user
        if not user.check_password(current_password):
            raise ValidationError({"current_password": "كلمة المرور الحالية غير صحيحة."})
        if new_password != password_confirm:
            raise ValidationError({"password_confirm": "كلمتا المرور غير متطابقتين."})
        try:
            password_validation.validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)}) from exc
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        user.device_sessions.filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now(), updated_at=timezone.now(),
        )
        Token.objects.filter(user=user).delete()
        return Response({"message": "تم تغيير كلمة المرور وإبطال جميع الجلسات؛ سجل الدخول مجدداً."})


class DeviceSessionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from apps.accounts.models import DeviceSession

        now = timezone.now()
        sessions = DeviceSession.objects.filter(
            user=request.user, revoked_at__isnull=True, expires_at__gt=now,
        ).order_by("-last_used_at", "-created_at")
        current_id = getattr(request.auth, "pk", None)
        return Response({"results": [{
            "id": str(item.pk),
            "device_id": item.device_id,
            "device_name": item.device_name,
            "user_agent": item.user_agent,
            "ip_address": item.ip_address,
            "created_at": item.created_at,
            "last_used_at": item.last_used_at,
            "expires_at": item.expires_at,
            "is_current": item.pk == current_id,
        } for item in sessions]})


class DeviceSessionRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id, *args, **kwargs):
        from apps.accounts.session_services import revoke_device_session

        count = revoke_device_session(user=request.user, session_id=session_id)
        if not count:
            return Response({"error": "الجلسة غير موجودة أو سبق إبطالها."}, status=404)
        return Response({"message": "تم إبطال جلسة الجهاز المحدد."})


class DeviceSessionsRevokeAllAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from apps.accounts.session_services import revoke_device_session
        from rest_framework.authtoken.models import Token

        count = revoke_device_session(user=request.user)
        legacy_count, _ = Token.objects.filter(user=request.user).delete()
        return Response({
            "message": "تم إبطال جميع الجلسات ورموز الدخول القديمة.",
            "revoked_device_sessions": count,
            "revoked_legacy_tokens": legacy_count,
        })


class DeviceSessionRefreshAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import DeviceSession
        from apps.accounts.session_services import rotate_device_session

        if not isinstance(request.auth, DeviceSession):
            raise ValidationError("تجديد الجلسة متاح لرموز الأجهزة الجديدة فقط؛ سجل الدخول مجدداً.")
        session, raw_token = rotate_device_session(request.auth)
        return Response({
            "access_token": raw_token,
            "token": raw_token,
            "token_type": "Bearer",
            "session_id": str(session.pk),
            "expires_at": session.expires_at.isoformat(),
        })


class APILogoutView(APIView):
    """Revoke only the authenticated device session; legacy tokens retain old semantics."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import DeviceSession
        from rest_framework.authtoken.models import Token

        if isinstance(request.auth, DeviceSession):
            request.auth.revoked_at = timezone.now()
            request.auth.save(update_fields=["revoked_at", "updated_at"])
        elif isinstance(request.auth, Token):
            request.auth.delete()
        return Response({"message": "تم تسجيل الخروج وإبطال جلسة المصادقة الحالية."})
