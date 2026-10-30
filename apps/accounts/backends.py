"""Permission backend for explicit central platform grants."""
from apps.accounts.services import has_platform_permission


class PlatformAccessBackend:
    def authenticate(self, request, **credentials):
        return None

    def get_user(self, user_id):
        from apps.accounts.models import User
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def has_perm(self, user_obj, perm, obj=None):
        if obj is not None:
            return False
        return has_platform_permission(user=user_obj, permission=perm)

    def has_module_perms(self, user_obj, app_label):
        if not user_obj or not user_obj.is_authenticated:
            return False
        if user_obj.is_superuser:
            return True
        from apps.accounts.models import PlatformAccess
        accesses = PlatformAccess.objects.filter(user=user_obj, is_active=True)
        if accesses.filter(role__in=[PlatformAccess.Role.OWNER, PlatformAccess.Role.OPERATIONS]).exists():
            return True
        return accesses.filter(permissions__content_type__app_label=app_label).exists()
