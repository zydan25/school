from rest_framework.permissions import BasePermission

from apps.accounts.services import has_school_permission


class HasActiveSchoolContext(BasePermission):
    message = "اختر مدرسة نشطة تملك عضوية فيها."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request, "school", None))


class HasSchoolPermission(BasePermission):
    """Set `required_school_permission = 'app_label.codename'` on the API view."""

    def has_permission(self, request, view):
        permission = getattr(view, "required_school_permission", None)
        if not permission:
            return False
        school = getattr(request, "school", None)
        return has_school_permission(user=request.user, school=school, permission=permission)
