"""
apps/platform/permissions.py
Permission classes for plan-based feature entitlement enforcement in DRF.
Prevents schools from using features/modules (WhatsApp, AI, HR, Accounting)
if the feature is not included in their subscription plan or has been disabled.
"""
from rest_framework import permissions, exceptions
from apps.platform.services import school_has_feature


class HasRequiredFeature(permissions.BasePermission):
    """
    التحقق من تفعيل الميزة المطلوبة في باقة اشتراك المدرسة أو عبر الاستثناءات.
    ترجع رسالة خطأ واضحة باللغة العربية مع كود 'feature_disabled' إذا كانت الميزة معطلة.
    """
    required_feature_code: str = ""

    def __init__(self, feature_code: str = ""):
        if feature_code:
            self.required_feature_code = feature_code

    def has_permission(self, request, view):
        # Allow superusers and platform operators full access
        if request.user and request.user.is_superuser:
            return True

        school = getattr(request, "school", None)
        if not school:
            membership = getattr(request, "school_membership", None)
            if membership:
                school = membership.school
            elif request.user.is_authenticated:
                active_mem = request.user.memberships.filter(is_active=True).first()
                if active_mem:
                    school = active_mem.school

        if not school:
            return True  # If no school context, handled by school context middleware

        feature_code = self.required_feature_code or getattr(view, "required_feature_code", "")
        if not feature_code:
            return True

        if not school_has_feature(school, feature_code):
            raise exceptions.PermissionDenied(
                detail={
                    "error": "الميزة غير مفعلة",
                    "detail": f"ميزة '{feature_code}' غير مفعلة في اشتراك مدرستكم الحالي. يرجى التواصل مع إدارة المنصة أو ترقية الباقة.",
                    "code": "feature_disabled",
                    "feature": feature_code,
                    "school": school.code,
                }
            )

        return True
