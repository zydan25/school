"""Permission-aware, bilingual-ready navigation policies for Unfold admin sites."""
def _central_check(permission):
    def check(request):
        if not request.path.startswith("/admin/"):
            return False
        from apps.accounts.services import has_platform_permission
        return has_platform_permission(user=request.user, permission=permission)
    return check


def _school_check(permission):
    def check(request):
        if not request.path.startswith("/school-admin/") or getattr(request, "school", None) is None:
            return False
        from apps.accounts.services import has_school_permission, is_platform_operator
        if is_platform_operator(request.user):
            return True
        return has_school_permission(user=request.user, school=request.school, permission=permission)
    return check


def central_navigation():
    """Build central links lazily after Django's URL namespace is ready."""
    from django.urls import reverse_lazy
    from django.utils.translation import gettext_lazy as _

    return [
        {
            "title": _("إدارة المنصة"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("لوحة المنصة"), "icon": "dashboard", "link": reverse_lazy("admin:index"), "permission": _central_check("tenants.view_school")},
                {"title": _("المدارس والمؤسسات"), "icon": "school", "link": reverse_lazy("admin:tenants_school_changelist"), "permission": _central_check("tenants.view_school")},
                {"title": _("الفروع"), "icon": "domain", "link": reverse_lazy("admin:tenants_branch_changelist"), "permission": _central_check("tenants.view_branch")},
                {"title": _("النطاقات"), "icon": "language", "link": reverse_lazy("admin:tenants_schooldomain_changelist"), "permission": _central_check("tenants.view_schooldomain")},
                {"title": _("إعدادات المدارس"), "icon": "tune", "link": reverse_lazy("admin:tenants_schoolsettings_changelist"), "permission": _central_check("tenants.view_schoolsettings")},
            ],
        },
        {
            "title": _("المستخدمون والصلاحيات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("حسابات المستخدمين"), "icon": "group", "link": reverse_lazy("admin:accounts_user_changelist"), "permission": _central_check("accounts.view_user")},
                {"title": _("صلاحيات المنصة"), "icon": "admin_panel_settings", "link": reverse_lazy("admin:accounts_platformaccess_changelist"), "permission": _central_check("accounts.view_platformaccess")},
                {"title": _("عضويات المدارس"), "icon": "groups", "link": reverse_lazy("admin:accounts_schoolmembership_changelist"), "permission": _central_check("accounts.view_schoolmembership")},
                {"title": _("الأدوار المدرسية"), "icon": "badge", "link": reverse_lazy("admin:accounts_schoolrole_changelist"), "permission": _central_check("accounts.view_schoolrole")},
                {"title": _("دعوات الانضمام"), "icon": "mail", "link": reverse_lazy("admin:accounts_schoolinvitation_changelist"), "permission": _central_check("accounts.view_schoolinvitation")},
            ],
        },
        {
            "title": _("الباقات والاشتراكات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("كتالوج المزايا"), "icon": "extension", "link": reverse_lazy("admin:platform_feature_changelist"), "permission": _central_check("platform.view_feature")},
                {"title": _("الباقات"), "icon": "inventory_2", "link": reverse_lazy("admin:platform_plan_changelist"), "permission": _central_check("platform.view_plan")},
                {"title": _("الاشتراكات"), "icon": "subscriptions", "link": reverse_lazy("admin:platform_subscription_changelist"), "permission": _central_check("platform.view_subscription")},
                {"title": _("فواتير المنصة"), "icon": "receipt_long", "link": reverse_lazy("admin:platform_platforminvoice_changelist"), "permission": _central_check("platform.view_platforminvoice")},
                {"title": _("دفعات الاشتراكات"), "icon": "payments", "link": reverse_lazy("admin:platform_platformpayment_changelist"), "permission": _central_check("platform.view_platformpayment")},
            ],
        },
        {
            "title": _("الحوكمة والإشعارات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("سجل التدقيق"), "icon": "shield", "link": reverse_lazy("admin:auditlog_auditevent_changelist"), "permission": _central_check("auditlog.view_auditevent")},
                {"title": _("الإشعارات"), "icon": "notifications", "link": reverse_lazy("admin:notifications_notification_changelist"), "permission": _central_check("notifications.view_notification")},
                {"title": _("قوالب الإشعار"), "icon": "drafts", "link": reverse_lazy("admin:notifications_notificationtemplate_changelist"), "permission": _central_check("notifications.view_notificationtemplate")},
            ],
        },
    ]


def school_navigation():
    from django.urls import reverse_lazy
    from django.utils.translation import gettext_lazy as _

    return [
        {
            "title": _("المدرسة والتشغيل"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("لوحة المدرسة"), "icon": "dashboard", "link": reverse_lazy("school_admin:index"), "permission": _school_check("tenants.view_branch")},
                {"title": _("الفروع"), "icon": "domain", "link": reverse_lazy("school_admin:tenants_branch_changelist"), "permission": _school_check("tenants.view_branch")},
                {"title": _("المستخدمون والعضويات"), "icon": "groups", "link": reverse_lazy("school_admin:accounts_schoolmembership_changelist"), "permission": _school_check("accounts.view_schoolmembership")},
                {"title": _("الأدوار والصلاحيات"), "icon": "admin_panel_settings", "link": reverse_lazy("school_admin:accounts_schoolrole_changelist"), "permission": _school_check("accounts.view_schoolrole")},
                {"title": _("دعوات الانضمام"), "icon": "mail", "link": reverse_lazy("school_admin:accounts_schoolinvitation_changelist"), "permission": _school_check("accounts.view_schoolinvitation")},
            ],
        },
        {
            "title": _("الهيكل الأكاديمي"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("السنوات الدراسية"), "icon": "calendar_month", "link": reverse_lazy("school_admin:academics_academicyear_changelist"), "permission": _school_check("academics.view_academicyear")},
                {"title": _("الفصول الدراسية"), "icon": "event_note", "link": reverse_lazy("school_admin:academics_academicterm_changelist"), "permission": _school_check("academics.view_academicterm")},
                {"title": _("المراحل التعليمية"), "icon": "account_tree", "link": reverse_lazy("school_admin:academics_educationalstage_changelist"), "permission": _school_check("academics.view_educationalstage")},
                {"title": _("الصفوف الدراسية"), "icon": "school", "link": reverse_lazy("school_admin:academics_gradelevel_changelist"), "permission": _school_check("academics.view_gradelevel")},
                {"title": _("الشعب والفصول"), "icon": "meeting_room", "link": reverse_lazy("school_admin:academics_section_changelist"), "permission": _school_check("academics.view_section")},
                {"title": _("القاعات والغرف"), "icon": "door_front", "link": reverse_lazy("school_admin:academics_classroom_changelist"), "permission": _school_check("academics.view_classroom")},
                {"title": _("المواد الدراسية"), "icon": "menu_book", "link": reverse_lazy("school_admin:academics_subject_changelist"), "permission": _school_check("academics.view_subject")},
                {"title": _("فترات الحصص"), "icon": "schedule", "link": reverse_lazy("school_admin:academics_perioddefinition_changelist"), "permission": _school_check("academics.view_perioddefinition")},
                {"title": _("أيام الدوام"), "icon": "today", "link": reverse_lazy("school_admin:academics_schoolworkingday_changelist"), "permission": _school_check("academics.view_schoolworkingday")},
            ],
        },
        {
            "title": _("الإشعارات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("إشعارات المدرسة"), "icon": "notifications", "link": reverse_lazy("school_admin:notifications_notification_changelist"), "permission": _school_check("notifications.view_notification")},
                {"title": _("قوالب الإشعار"), "icon": "drafts", "link": reverse_lazy("school_admin:notifications_notificationtemplate_changelist"), "permission": _school_check("notifications.view_notificationtemplate")},
                {"title": _("تفضيلات الإشعار"), "icon": "notifications_active", "link": reverse_lazy("school_admin:notifications_notificationpreference_changelist"), "permission": _school_check("notifications.view_notificationpreference")},
            ],
        },
    ]
