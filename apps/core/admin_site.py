"""Branded Unfold site used for central platform administration."""
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from unfold.sites import UnfoldAdminSite

from apps.accounts.models import PlatformAccess


class PlatformAdminAuthenticationForm(AdminAuthenticationForm):
    """Allow named platform operators without requiring the broad Django is_staff flag."""
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(_("هذا الحساب غير مفعل."), code="inactive")
        if user.is_superuser:
            return
        if not PlatformAccess.objects.filter(user=user, is_active=True).exists():
            raise ValidationError(_("لا توجد صلاحية مركزية نشطة لهذا الحساب."), code="no_platform_access")


class PlatformAdminSite(UnfoldAdminSite):
    site_header = "سكول | الإدارة المركزية"
    site_title = "الإدارة المركزية - سكول"
    index_title = "مركز إدارة المنصة"
    login_form = PlatformAdminAuthenticationForm

    def has_permission(self, request):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return False
        return user.is_superuser or PlatformAccess.objects.filter(user=user, is_active=True).exists()

    def each_context(self, request):
        context = super().each_context(request)
        context.update({
            "site_header": self.site_header,
            "site_title": self.site_title,
            "title": self.index_title,
        })
        return context
