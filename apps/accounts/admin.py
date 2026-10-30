from apps.core.admin import AuditedAdminMixin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.accounts.models import MembershipRole, PlatformAccess, SchoolInvitation, SchoolMembership, SchoolRole, User
from apps.auditlog.services import record_event


class PlatformUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("phone", "first_name", "middle_name", "last_name", "email")


class PlatformUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class MembershipRoleInline(TabularInline):
    model = MembershipRole
    extra = 0
    autocomplete_fields = ("role", "assigned_by")
    readonly_fields = ("created_at", "updated_at")
    fields = ("role", "valid_from", "valid_until", "assigned_by")


@admin.register(User)
class UserAdmin(AuditedAdminMixin, DjangoUserAdmin, ModelAdmin):
    form = PlatformUserChangeForm
    add_form = PlatformUserCreationForm
    ordering = ("first_name", "last_name")
    list_display = ("full_name", "phone", "email", "status", "is_staff", "is_platform_admin", "last_login")
    list_filter = ("status", "is_active", "is_staff", "is_platform_admin", "preferred_language")
    search_fields = ("phone", "email", "first_name", "middle_name", "last_name", "full_name")
    list_select_related = False
    list_per_page = 40
    date_hierarchy = "created_at"
    readonly_fields = ("id", "full_name", "last_login", "created_at", "updated_at", "phone_verified_at", "email_verified_at", "last_seen_at")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (_("البيانات الشخصية"), {"fields": ("id", "phone", "email", "first_name", "middle_name", "last_name", "full_name", "avatar", "preferred_language", "timezone")}),
        (_("حالة الحساب والتحقق"), {"fields": ("status", "is_active", "is_staff", "is_platform_admin", "phone_verified_at", "email_verified_at", "failed_login_count", "locked_until", "last_seen_at")}),
        (_("أمن وصلاحيات Django"), {"classes": ("collapse",), "fields": ("password", "last_login", "is_superuser", "groups", "user_permissions")}),
        (_("التواريخ"), {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (_("إنشاء حساب مستخدم"), {"classes": ("wide",), "fields": ("phone", "email", "first_name", "middle_name", "last_name", "password1", "password2", "is_active", "is_staff", "is_platform_admin")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PlatformAccess)
class PlatformAccessAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("user", "role", "is_active", "granted_by", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__phone", "user__full_name", "user__email", "notes")
    autocomplete_fields = ("user", "granted_by")
    filter_horizontal = ("permissions",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("school", "user", "status", "is_default", "joined_at", "expires_at")
    list_filter = ("status", "is_default", "school__status")
    search_fields = ("school__name", "school__code", "user__phone", "user__full_name", "user__email")
    autocomplete_fields = ("school", "user", "invited_by")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (MembershipRoleInline,)
    list_select_related = ("school", "user")
    date_hierarchy = "joined_at"
    actions = ("activate_memberships", "suspend_memberships")

    @admin.action(description="تفعيل العضويات المحددة")
    def activate_memberships(self, request, queryset):
        count = 0
        for membership in queryset.select_related("school", "user"):
            membership.activate()
            record_event(action="membership.activated", description="تفعيل عضوية مدرسة", actor=request.user, school=membership.school, obj=membership, request=request)
            count += 1
        self.message_user(request, f"تم تفعيل {count} عضوية.")

    @admin.action(description="إيقاف العضويات المحددة")
    def suspend_memberships(self, request, queryset):
        count = 0
        for membership in queryset.select_related("school", "user"):
            membership.status = SchoolMembership.Status.SUSPENDED
            membership.is_default = False
            membership.save(update_fields=["status", "is_default", "updated_at"])
            record_event(
                action="membership.suspended",
                description="إيقاف عضوية مدرسة من الإدارة المركزية",
                actor=request.user, school=membership.school, obj=membership, request=request,
            )
            count += 1
        self.message_user(request, f"تم إيقاف {count} عضوية.")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SchoolRole)
class SchoolRoleAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "school", "is_system", "is_active", "is_archived")
    list_filter = ("is_system", "is_active", "is_archived", "school")
    search_fields = ("name", "code", "school__name", "description")
    autocomplete_fields = ("school",)
    filter_horizontal = ("permissions",)
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("school",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MembershipRole)
class MembershipRoleAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("membership", "role", "valid_from", "valid_until", "assigned_by")
    search_fields = ("membership__user__full_name", "membership__user__phone", "role__name", "membership__school__name")
    autocomplete_fields = ("membership", "role", "assigned_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolInvitation)
class SchoolInvitationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("email", "school", "status", "expires_at", "invited_by", "accepted_at")
    list_filter = ("status", "school")
    search_fields = ("email", "phone", "school__name", "school__code")
    autocomplete_fields = ("school", "invited_by", "accepted_by")
    filter_horizontal = ("roles",)
    readonly_fields = ("id", "token_digest", "created_at", "updated_at", "accepted_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        # Invitation tokens must be created and delivered through issue_school_invitation().
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")
