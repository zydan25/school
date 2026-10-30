"""Permission-aware, bilingual-ready navigation policies for Unfold admin sites."""
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


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
    """Build complete central platform links lazily after Django's URL namespace is ready."""
    return [
        {
            "title": _("إدارة المنصة والمدارس"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("لوحة المنصة المركزية"), "icon": "dashboard", "link": reverse_lazy("admin:index"), "permission": _central_check("tenants.view_school")},
                {"title": _("بوابة إدارة المدرسة (School Admin)"), "icon": "open_in_new", "link": "/school-admin/", "permission": _central_check("tenants.view_school")},
                {"title": _("المدارس والمؤسسات"), "icon": "school", "link": reverse_lazy("admin:tenants_school_changelist"), "permission": _central_check("tenants.view_school")},
                {"title": _("الفروع المدرسية"), "icon": "domain", "link": reverse_lazy("admin:tenants_branch_changelist"), "permission": _central_check("tenants.view_branch")},
                {"title": _("النطاقات والدومينات"), "icon": "language", "link": reverse_lazy("admin:tenants_schooldomain_changelist"), "permission": _central_check("tenants.view_schooldomain")},
                {"title": _("إعدادات المدارس"), "icon": "tune", "link": reverse_lazy("admin:tenants_schoolsettings_changelist"), "permission": _central_check("tenants.view_schoolsettings")},
            ],
        },
        {
            "title": _("المستخدمون والصلاحيات والعضويات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("حسابات المستخدمين"), "icon": "group", "link": reverse_lazy("admin:accounts_user_changelist"), "permission": _central_check("accounts.view_user")},
                {"title": _("صلاحيات المنصة"), "icon": "admin_panel_settings", "link": reverse_lazy("admin:accounts_platformaccess_changelist"), "permission": _central_check("accounts.view_platformaccess")},
                {"title": _("عضويات المدارس"), "icon": "groups", "link": reverse_lazy("admin:accounts_schoolmembership_changelist"), "permission": _central_check("accounts.view_schoolmembership")},
                {"title": _("الأدوار المدرسية"), "icon": "badge", "link": reverse_lazy("admin:accounts_schoolrole_changelist"), "permission": _central_check("accounts.view_schoolrole")},
                {"title": _("دعوات الانضمام"), "icon": "mail", "link": reverse_lazy("admin:accounts_schoolinvitation_changelist"), "permission": _central_check("accounts.view_schoolinvitation")},
            ],
        },
        {
            "title": _("الباقات والاشتراكات المالية"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("كتالوج المزايا"), "icon": "extension", "link": reverse_lazy("admin:platform_feature_changelist"), "permission": _central_check("platform.view_feature")},
                {"title": _("الباقات والخطط"), "icon": "inventory_2", "link": reverse_lazy("admin:platform_plan_changelist"), "permission": _central_check("platform.view_plan")},
                {"title": _("اشتراكات المدارس"), "icon": "subscriptions", "link": reverse_lazy("admin:platform_subscription_changelist"), "permission": _central_check("platform.view_subscription")},
                {"title": _("فواتير المنصة"), "icon": "receipt_long", "link": reverse_lazy("admin:platform_platforminvoice_changelist"), "permission": _central_check("platform.view_platforminvoice")},
                {"title": _("دفعات الاشتراكات"), "icon": "payments", "link": reverse_lazy("admin:platform_platformpayment_changelist"), "permission": _central_check("platform.view_platformpayment")},
            ],
        },
        {
            "title": _("الهيكل الأكاديمي والتعليمي"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("السنوات الدراسية"), "icon": "calendar_month", "link": reverse_lazy("admin:academics_academicyear_changelist"), "permission": _central_check("academics.view_academicyear")},
                {"title": _("الفصول الدراسية"), "icon": "event_note", "link": reverse_lazy("admin:academics_academicterm_changelist"), "permission": _central_check("academics.view_academicterm")},
                {"title": _("المراحل التعليمية"), "icon": "account_tree", "link": reverse_lazy("admin:academics_educationalstage_changelist"), "permission": _central_check("academics.view_educationalstage")},
                {"title": _("الصفوف الدراسية"), "icon": "school", "link": reverse_lazy("admin:academics_gradelevel_changelist"), "permission": _central_check("academics.view_gradelevel")},
                {"title": _("الشعب والفصول"), "icon": "meeting_room", "link": reverse_lazy("admin:academics_section_changelist"), "permission": _central_check("academics.view_section")},
                {"title": _("المواد الدراسية"), "icon": "menu_book", "link": reverse_lazy("admin:academics_subject_changelist"), "permission": _central_check("academics.view_subject")},
                {"title": _("القاعات والغرف"), "icon": "door_front", "link": reverse_lazy("admin:academics_classroom_changelist"), "permission": _central_check("academics.view_classroom")},
                {"title": _("فترات الحصص"), "icon": "schedule", "link": reverse_lazy("admin:academics_perioddefinition_changelist"), "permission": _central_check("academics.view_perioddefinition")},
                {"title": _("أيام الدوام المدرسي"), "icon": "today", "link": reverse_lazy("admin:academics_schoolworkingday_changelist"), "permission": _central_check("academics.view_schoolworkingday")},
            ],
        },
        {
            "title": _("الكادر والمعلمون والمشرفون"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("المعلمون"), "icon": "badge", "link": reverse_lazy("admin:staff_teacher_changelist"), "permission": _central_check("staff.view_teacher")},
                {"title": _("الكادر الإداري ومشرفو الأدوار"), "icon": "manage_accounts", "link": reverse_lazy("admin:staff_staffmember_changelist"), "permission": _central_check("staff.view_staffmember")},
                {"title": _("إسناد المواد والشعب"), "icon": "assignment_ind", "link": reverse_lazy("admin:staff_teacherassignment_changelist"), "permission": _central_check("staff.view_teacherassignment")},
            ],
        },
        {
            "title": _("الطلاب وأولياء الأمور والمتابعة السلوكية"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("سجل الطلاب"), "icon": "person", "link": reverse_lazy("admin:students_student_changelist"), "permission": _central_check("students.view_student")},
                {"title": _("أولياء الأمور"), "icon": "family_restroom", "link": reverse_lazy("admin:students_guardian_changelist"), "permission": _central_check("students.view_guardian")},
                {"title": _("روابط الطلاب بالأسر"), "icon": "people", "link": reverse_lazy("admin:students_studentguardianrelation_changelist"), "permission": _central_check("students.view_studentguardianrelation")},
                {"title": _("تقارير الوقائع السلوكية"), "icon": "report_problem", "link": reverse_lazy("admin:students_studentincidentreport_changelist"), "permission": _central_check("students.view_studentincidentreport")},
                {"title": _("الاستدعاءات الإدارية"), "icon": "gavel", "link": reverse_lazy("admin:students_administrativesummon_changelist"), "permission": _central_check("students.view_administrativesummon")},
                {"title": _("صندوق الشكاوى والمقترحات"), "icon": "feedback", "link": reverse_lazy("admin:students_schoolcomplaint_changelist"), "permission": _central_check("students.view_schoolcomplaint")},
            ],
        },
        {
            "title": _("الجدول المدرسي والتدريس والذكاء الاصطناعي"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("جدول الحصص الأسبوعي"), "icon": "calendar_month", "link": reverse_lazy("admin:timetable_classschedule_changelist"), "permission": _central_check("timetable.view_classschedule")},
                {"title": _("سجلات الدروس اليومية"), "icon": "history_edu", "link": reverse_lazy("admin:timetable_dailylessonlog_changelist"), "permission": _central_check("timetable.view_dailylessonlog")},
                {"title": _("وثائق المناهج (RAG)"), "icon": "menu_book", "link": reverse_lazy("admin:copilot_curriculumdocument_changelist"), "permission": _central_check("copilot.view_curriculumdocument")},
                {"title": _("جلسات المساعد الذكي"), "icon": "smart_toy", "link": reverse_lazy("admin:copilot_aichatsession_changelist"), "permission": _central_check("copilot.view_aichatsession")},
            ],
        },
        {
            "title": _("الواجبات والاختبارات وبنك الأسئلة والكنترول"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("الواجبات المدرسية"), "icon": "assignment", "link": reverse_lazy("admin:assignments_homework_changelist"), "permission": _central_check("assignments.view_homework")},
                {"title": _("تسليمات الطلاب للواجبات"), "icon": "task_alt", "link": reverse_lazy("admin:assignments_homeworksubmission_changelist"), "permission": _central_check("assignments.view_homeworksubmission")},
                {"title": _("بنك الأسئلة المركزي"), "icon": "quiz", "link": reverse_lazy("admin:assessments_questionbank_changelist"), "permission": _central_check("assessments.view_questionbank")},
                {"title": _("الاختبارات الإلكترونية"), "icon": "devices", "link": reverse_lazy("admin:assessments_onlineexam_changelist"), "permission": _central_check("assessments.view_onlineexam")},
                {"title": _("تسليمات الاختبارات الإلكترونية"), "icon": "fact_check", "link": reverse_lazy("admin:assessments_studentonlineexamsubmission_changelist"), "permission": _central_check("assessments.view_studentonlineexamsubmission")},
                {"title": _("أنواع التقييمات والاختبارات"), "icon": "category", "link": reverse_lazy("admin:assessments_assessmenttype_changelist"), "permission": _central_check("assessments.view_assessmenttype")},
                {"title": _("دفتر الدرجات والنتائج"), "icon": "grade", "link": reverse_lazy("admin:assessments_gradebook_changelist"), "permission": _central_check("assessments.view_gradebook")},
                {"title": _("لجان الامتحانات والكنترول"), "icon": "co_present", "link": reverse_lazy("admin:assessments_examcommittee_changelist"), "permission": _central_check("assessments.view_examcommittee")},
                {"title": _("أرقام الجلوس والكنترول"), "icon": "pin", "link": reverse_lazy("admin:assessments_examseating_changelist"), "permission": _central_check("assessments.view_examseating")},
            ],
        },
        {
            "title": _("الحضور والانضباط المدرسي"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("الحضور والغياب اليومي"), "icon": "how_to_reg", "link": reverse_lazy("admin:attendance_dailyattendance_changelist"), "permission": _central_check("attendance.view_dailyattendance")},
                {"title": _("حضور الحصص الدراسية"), "icon": "event_available", "link": reverse_lazy("admin:attendance_periodattendance_changelist"), "permission": _central_check("attendance.view_periodattendance")},
            ],
        },
        {
            "title": _("الرسوم المدرسية والتحصيل والأقساط"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("فواتير الطلاب"), "icon": "receipt", "link": reverse_lazy("admin:student_fees_studentinvoice_changelist"), "permission": _central_check("student_fees.view_studentinvoice")},
                {"title": _("سندات القبض والتحصيل"), "icon": "payments", "link": reverse_lazy("admin:student_fees_paymentreceipt_changelist"), "permission": _central_check("student_fees.view_paymentreceipt")},
                {"title": _("دفتر تخصيص الدفعات"), "icon": "account_balance_wallet", "link": reverse_lazy("admin:student_fees_paymentallocation_changelist"), "permission": _central_check("student_fees.view_paymentallocation")},
                {"title": _("خطط تقسيط الرسوم"), "icon": "credit_card", "link": reverse_lazy("admin:student_fees_feeinstallmentplan_changelist"), "permission": _central_check("student_fees.view_feeinstallmentplan")},
                {"title": _("الأقساط المالية المجدولة"), "icon": "pending_actions", "link": reverse_lazy("admin:student_fees_feeinstallment_changelist"), "permission": _central_check("student_fees.view_feeinstallment")},
                {"title": _("هياكل الرسوم السنوية"), "icon": "price_change", "link": reverse_lazy("admin:student_fees_feestructure_changelist"), "permission": _central_check("student_fees.view_feestructure")},
                {"title": _("بنود وتصنيفات الرسوم"), "icon": "category", "link": reverse_lazy("admin:student_fees_feecategory_changelist"), "permission": _central_check("student_fees.view_feecategory")},
            ],
        },
        {
            "title": _("المحاسبة المدرسية والدفاتر المالية"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("دليل وشجرة الحسابات"), "icon": "account_balance", "link": reverse_lazy("admin:accounting_account_changelist"), "permission": _central_check("accounting.view_account")},
                {"title": _("قيود اليومية العامة"), "icon": "menu_book", "link": reverse_lazy("admin:accounting_journalentry_changelist"), "permission": _central_check("accounting.view_journalentry")},
                {"title": _("سندات الصرف المالي"), "icon": "receipt_long", "link": reverse_lazy("admin:accounting_paymentvoucher_changelist"), "permission": _central_check("accounting.view_paymentvoucher")},
                {"title": _("سندات القبض العامة"), "icon": "price_check", "link": reverse_lazy("admin:accounting_receiptvoucher_changelist"), "permission": _central_check("accounting.view_receiptvoucher")},
                {"title": _("تصنيفات المصروفات"), "icon": "category", "link": reverse_lazy("admin:accounting_expensecategory_changelist"), "permission": _central_check("accounting.view_expensecategory")},
                {"title": _("السنوات المالية"), "icon": "date_range", "link": reverse_lazy("admin:accounting_fiscalyear_changelist"), "permission": _central_check("accounting.view_fiscalyear")},
                {"title": _("مراكز التكلفة"), "icon": "pie_chart", "link": reverse_lazy("admin:accounting_costcenter_changelist"), "permission": _central_check("accounting.view_costcenter")},
            ],
        },
        {
            "title": _("إدارة الرواتب وشؤون الموظفين المالية"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("عقود الموظفين والرواتب"), "icon": "badge", "link": reverse_lazy("admin:payroll_employeecontract_changelist"), "permission": _central_check("payroll.view_employeecontract")},
                {"title": _("مسيرات الرواتب الشهرية"), "icon": "payments", "link": reverse_lazy("admin:payroll_payrollrun_changelist"), "permission": _central_check("payroll.view_payrollrun")},
                {"title": _("قسائم رواتب الموظفين"), "icon": "request_quote", "link": reverse_lazy("admin:payroll_payslip_changelist"), "permission": _central_check("payroll.view_payslip")},
                {"title": _("سلف وقروض الموظفين"), "icon": "credit_card", "link": reverse_lazy("admin:payroll_employeeloanadvance_changelist"), "permission": _central_check("payroll.view_employeeloanadvance")},
            ],
        },
        {
            "title": _("المشتريات والمستودعات والمخزون"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("الموردون والشركات المعتمدة"), "icon": "local_shipping", "link": reverse_lazy("admin:inventory_supplier_changelist"), "permission": _central_check("inventory.view_supplier")},
                {"title": _("المستودعات والمخازن"), "icon": "store", "link": reverse_lazy("admin:inventory_warehouse_changelist"), "permission": _central_check("inventory.view_warehouse")},
                {"title": _("دليل الأصناف والمواد والكتب"), "icon": "inventory", "link": reverse_lazy("admin:inventory_inventoryitem_changelist"), "permission": _central_check("inventory.view_inventoryitem")},
                {"title": _("سجل حركات المخزون"), "icon": "swap_horiz", "link": reverse_lazy("admin:inventory_stockmovement_changelist"), "permission": _central_check("inventory.view_stockmovement")},
                {"title": _("أوامر الشراء والتوريد"), "icon": "shopping_cart", "link": reverse_lazy("admin:inventory_purchaseorder_changelist"), "permission": _central_check("inventory.view_purchaseorder")},
            ],
        },
        {
            "title": _("الأصول الثابتة والإهلاك"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("سجل الأصول الثابتة والعهد"), "icon": "devices", "link": reverse_lazy("admin:assets_fixedasset_changelist"), "permission": _central_check("assets.view_fixedasset")},
                {"title": _("تصنيفات الأصول"), "icon": "category", "link": reverse_lazy("admin:assets_assetcategory_changelist"), "permission": _central_check("assets.view_assetcategory")},
                {"title": _("سجلات الإهلاك الدوري"), "icon": "trending_down", "link": reverse_lazy("admin:assets_assetdepreciationentry_changelist"), "permission": _central_check("assets.view_assetdepreciationentry")},
            ],
        },
        {
            "title": _("الخدمات المدرسية المساندة"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("خطوط النقل المدرسي والحافلات"), "icon": "directions_bus", "link": reverse_lazy("admin:school_services_busroute_changelist"), "permission": _central_check("school_services.view_busroute")},
                {"title": _("اشتراكات حافلات الطلاب"), "icon": "commute", "link": reverse_lazy("admin:school_services_studentbussubscription_changelist"), "permission": _central_check("school_services.view_studentbussubscription")},
                {"title": _("المحاسبة المالية للباصات والسائقين"), "icon": "account_balance_wallet", "link": reverse_lazy("admin:school_services_busfinancialsettlement_changelist"), "permission": _central_check("school_services.view_busfinancialsettlement")},
                {"title": _("أوامر صرف الكتب لمسؤول المخزن"), "icon": "local_shipping", "link": reverse_lazy("admin:school_services_bookrequisitionorder_changelist"), "permission": _central_check("school_services.view_bookrequisitionorder")},
                {"title": _("توزيع وتسليم الكتب المدرسية"), "icon": "auto_stories", "link": reverse_lazy("admin:school_services_studentbookdistribution_changelist"), "permission": _central_check("school_services.view_studentbookdistribution")},
                {"title": _("المكتبة المدرسية والكتب"), "icon": "local_library", "link": reverse_lazy("admin:school_services_librarybook_changelist"), "permission": _central_check("school_services.view_librarybook")},
                {"title": _("سجل إعارات واسترجاع الكتب"), "icon": "menu_book", "link": reverse_lazy("admin:school_services_bookloan_changelist"), "permission": _central_check("school_services.view_bookloan")},
                {"title": _("الملفات الصحية للطلاب"), "icon": "health_and_safety", "link": reverse_lazy("admin:school_services_studenthealthprofile_changelist"), "permission": _central_check("school_services.view_studenthealthprofile")},
                {"title": _("زيارات العيادة المدرسية"), "icon": "medical_services", "link": reverse_lazy("admin:school_services_clinicvisit_changelist"), "permission": _central_check("school_services.view_clinicvisit")},
            ],
        },
        {
            "title": _("الحوكمة والإشعارات وسجل التدقيق"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("سجل التدقيق والأمان"), "icon": "shield", "link": reverse_lazy("admin:auditlog_auditevent_changelist"), "permission": _central_check("auditlog.view_auditevent")},
                {"title": _("إشعارات النظام"), "icon": "notifications", "link": reverse_lazy("admin:notifications_notification_changelist"), "permission": _central_check("notifications.view_notification")},
                {"title": _("قوالب الإشعار"), "icon": "drafts", "link": reverse_lazy("admin:notifications_notificationtemplate_changelist"), "permission": _central_check("notifications.view_notificationtemplate")},
                {"title": _("بوابات الرسائل والواتساب"), "icon": "chat", "link": reverse_lazy("admin:notifications_schoolmessaginggateway_changelist"), "permission": _central_check("notifications.view_notification")},
            ],
        },
    ]


def school_navigation():
    """Build complete per-school admin links scoped to the active tenant."""
    return [
        {
            "title": _("المدرسة والتشغيل"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("لوحة إدارة المدرسة"), "icon": "dashboard", "link": reverse_lazy("school_admin:index"), "permission": _school_check("tenants.view_branch")},
                {"title": _("العودة للإدارة المركزية (Superadmin)"), "icon": "admin_panel_settings", "link": "/admin/", "permission": _school_check("tenants.view_branch")},
                {"title": _("الفروع المدرسية"), "icon": "domain", "link": reverse_lazy("school_admin:tenants_branch_changelist"), "permission": _school_check("tenants.view_branch")},
                {"title": _("المستخدمون والعضويات"), "icon": "groups", "link": reverse_lazy("school_admin:accounts_schoolmembership_changelist"), "permission": _school_check("accounts.view_schoolmembership")},
                {"title": _("الأدوار والصلاحيات"), "icon": "badge", "link": reverse_lazy("school_admin:accounts_schoolrole_changelist"), "permission": _school_check("accounts.view_schoolrole")},
                {"title": _("دعوات الانضمام"), "icon": "mail", "link": reverse_lazy("school_admin:accounts_schoolinvitation_changelist"), "permission": _school_check("accounts.view_schoolinvitation")},
            ],
        },
        {
            "title": _("الهيكل الأكاديمي والتعليمي"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("السنوات الدراسية"), "icon": "calendar_month", "link": reverse_lazy("school_admin:academics_academicyear_changelist"), "permission": _school_check("academics.view_academicyear")},
                {"title": _("الفصول الدراسية"), "icon": "event_note", "link": reverse_lazy("school_admin:academics_academicterm_changelist"), "permission": _school_check("academics.view_academicterm")},
                {"title": _("المراحل التعليمية"), "icon": "account_tree", "link": reverse_lazy("school_admin:academics_educationalstage_changelist"), "permission": _school_check("academics.view_educationalstage")},
                {"title": _("الصفوف الدراسية"), "icon": "school", "link": reverse_lazy("school_admin:academics_gradelevel_changelist"), "permission": _school_check("academics.view_gradelevel")},
                {"title": _("الشعب والفصول"), "icon": "meeting_room", "link": reverse_lazy("school_admin:academics_section_changelist"), "permission": _school_check("academics.view_section")},
                {"title": _("القاعات والغرف"), "icon": "door_front", "link": reverse_lazy("school_admin:academics_classroom_changelist"), "permission": _school_check("academics.view_classroom")},
                {"title": _("المواد الدراسية"), "icon": "menu_book", "link": reverse_lazy("school_admin:academics_subject_changelist"), "permission": _school_check("academics.view_subject")},
                {"title": _("فترات الحصص"), "icon": "schedule", "link": reverse_lazy("school_admin:academics_perioddefinition_changelist"), "permission": _school_check("academics.view_perioddefinition")},
                {"title": _("أيام الدوام المدرسي"), "icon": "today", "link": reverse_lazy("school_admin:academics_schoolworkingday_changelist"), "permission": _school_check("academics.view_schoolworkingday")},
            ],
        },
        {
            "title": _("الكادر والمعلمون والمشرفون"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("المعلمون"), "icon": "badge", "link": reverse_lazy("school_admin:staff_teacher_changelist"), "permission": _school_check("staff.view_teacher")},
                {"title": _("الكادر الإداري ومشرفو الأدوار"), "icon": "manage_accounts", "link": reverse_lazy("school_admin:staff_staffmember_changelist"), "permission": _school_check("staff.view_staffmember")},
                {"title": _("إسناد المواد والشعب"), "icon": "assignment_ind", "link": reverse_lazy("school_admin:staff_teacherassignment_changelist"), "permission": _school_check("staff.view_teacherassignment")},
            ],
        },
        {
            "title": _("الطلاب وأولياء الأمور والمتابعة السلوكية"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("سجل الطلاب"), "icon": "person", "link": reverse_lazy("school_admin:students_student_changelist"), "permission": _school_check("students.view_student")},
                {"title": _("أولياء الأمور"), "icon": "family_restroom", "link": reverse_lazy("school_admin:students_guardian_changelist"), "permission": _school_check("students.view_guardian")},
                {"title": _("تقارير الوقائع السلوكية"), "icon": "report_problem", "link": reverse_lazy("school_admin:students_studentincidentreport_changelist"), "permission": _school_check("students.view_studentincidentreport")},
                {"title": _("الاستدعاءات الإدارية"), "icon": "gavel", "link": reverse_lazy("school_admin:students_administrativesummon_changelist"), "permission": _school_check("students.view_administrativesummon")},
                {"title": _("صندوق الشكاوى والمقترحات"), "icon": "feedback", "link": reverse_lazy("school_admin:students_schoolcomplaint_changelist"), "permission": _school_check("students.view_schoolcomplaint")},
            ],
        },
        {
            "title": _("الجدول والتدريس والذكاء الاصطناعي"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("جدول الحصص"), "icon": "calendar_month", "link": reverse_lazy("school_admin:timetable_classschedule_changelist"), "permission": _school_check("timetable.view_classschedule")},
                {"title": _("سجلات الدروس اليومية"), "icon": "history_edu", "link": reverse_lazy("school_admin:timetable_dailylessonlog_changelist"), "permission": _school_check("timetable.view_dailylessonlog")},
                {"title": _("وثائق المناهج (RAG)"), "icon": "menu_book", "link": reverse_lazy("school_admin:copilot_curriculumdocument_changelist"), "permission": _school_check("copilot.view_curriculumdocument")},
                {"title": _("جلسات المحادثة الذكية"), "icon": "smart_toy", "link": reverse_lazy("school_admin:copilot_aichatsession_changelist"), "permission": _school_check("copilot.view_aichatsession")},
            ],
        },
        {
            "title": _("الواجبات والتقييمات وبنك الأسئلة والكنترول"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("الواجبات المدرسية"), "icon": "assignment", "link": reverse_lazy("school_admin:assignments_homework_changelist"), "permission": _school_check("assignments.view_homework")},
                {"title": _("تسليمات الطلاب"), "icon": "task_alt", "link": reverse_lazy("school_admin:assignments_homeworksubmission_changelist"), "permission": _school_check("assignments.view_homeworksubmission")},
                {"title": _("بنك الأسئلة المركزي"), "icon": "quiz", "link": reverse_lazy("school_admin:assessments_questionbank_changelist"), "permission": _school_check("assessments.view_questionbank")},
                {"title": _("الاختبارات الإلكترونية"), "icon": "devices", "link": reverse_lazy("school_admin:assessments_onlineexam_changelist"), "permission": _school_check("assessments.view_onlineexam")},
                {"title": _("تسليمات الاختبارات الإلكترونية"), "icon": "fact_check", "link": reverse_lazy("school_admin:assessments_studentonlineexamsubmission_changelist"), "permission": _school_check("assessments.view_studentonlineexamsubmission")},
                {"title": _("أنواع التقييم"), "icon": "category", "link": reverse_lazy("school_admin:assessments_assessmenttype_changelist"), "permission": _school_check("assessments.view_assessmenttype")},
                {"title": _("دفتر الدرجات والنتائج"), "icon": "grade", "link": reverse_lazy("school_admin:assessments_gradebook_changelist"), "permission": _school_check("assessments.view_gradebook")},
                {"title": _("لجان الامتحانات والكنترول"), "icon": "co_present", "link": reverse_lazy("school_admin:assessments_examcommittee_changelist"), "permission": _school_check("assessments.view_examcommittee")},
                {"title": _("أرقام الجلوس والكنترول"), "icon": "pin", "link": reverse_lazy("school_admin:assessments_examseating_changelist"), "permission": _school_check("assessments.view_examseating")},
            ],
        },
        {
            "title": _("الحضور والغياب"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("الحضور اليومي"), "icon": "how_to_reg", "link": reverse_lazy("school_admin:attendance_dailyattendance_changelist"), "permission": _school_check("attendance.view_dailyattendance")},
                {"title": _("حضور الحصص"), "icon": "event_available", "link": reverse_lazy("school_admin:attendance_periodattendance_changelist"), "permission": _school_check("attendance.view_periodattendance")},
            ],
        },
        {
            "title": _("الرسوم المدرسية والتحصيل والأقساط"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("فواتير الطلاب"), "icon": "receipt", "link": reverse_lazy("school_admin:student_fees_studentinvoice_changelist"), "permission": _school_check("student_fees.view_studentinvoice")},
                {"title": _("سندات القبض"), "icon": "payments", "link": reverse_lazy("school_admin:student_fees_paymentreceipt_changelist"), "permission": _school_check("student_fees.view_paymentreceipt")},
                {"title": _("دفتر تخصيص الدفعات"), "icon": "account_balance_wallet", "link": reverse_lazy("school_admin:student_fees_paymentallocation_changelist"), "permission": _school_check("student_fees.view_paymentallocation")},
                {"title": _("خطط تقسيط الرسوم"), "icon": "credit_card", "link": reverse_lazy("school_admin:student_fees_feeinstallmentplan_changelist"), "permission": _school_check("student_fees.view_feeinstallmentplan")},
                {"title": _("الأقساط المالية المجدولة"), "icon": "pending_actions", "link": reverse_lazy("school_admin:student_fees_feeinstallment_changelist"), "permission": _school_check("student_fees.view_feeinstallment")},
                {"title": _("هياكل الرسوم"), "icon": "price_change", "link": reverse_lazy("school_admin:student_fees_feestructure_changelist"), "permission": _school_check("student_fees.view_feestructure")},
                {"title": _("بنود الرسوم"), "icon": "category", "link": reverse_lazy("school_admin:student_fees_feecategory_changelist"), "permission": _school_check("student_fees.view_feecategory")},
            ],
        },
        {
            "title": _("المحاسبة المدرسية المستقلة"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("دليل وشجرة الحسابات"), "icon": "account_balance", "link": reverse_lazy("school_admin:accounting_account_changelist"), "permission": _school_check("accounting.view_account")},
                {"title": _("قيود اليومية العامة"), "icon": "menu_book", "link": reverse_lazy("school_admin:accounting_journalentry_changelist"), "permission": _school_check("accounting.view_journalentry")},
                {"title": _("سندات الصرف المالي"), "icon": "receipt_long", "link": reverse_lazy("school_admin:accounting_paymentvoucher_changelist"), "permission": _school_check("accounting.view_paymentvoucher")},
                {"title": _("سندات القبض العامة"), "icon": "price_check", "link": reverse_lazy("school_admin:accounting_receiptvoucher_changelist"), "permission": _school_check("accounting.view_receiptvoucher")},
                {"title": _("تصنيفات المصروفات"), "icon": "category", "link": reverse_lazy("school_admin:accounting_expensecategory_changelist"), "permission": _school_check("accounting.view_expensecategory")},
                {"title": _("السنوات المالية"), "icon": "date_range", "link": reverse_lazy("school_admin:accounting_fiscalyear_changelist"), "permission": _school_check("accounting.view_fiscalyear")},
                {"title": _("مراكز التكلفة"), "icon": "pie_chart", "link": reverse_lazy("school_admin:accounting_costcenter_changelist"), "permission": _school_check("accounting.view_costcenter")},
            ],
        },
        {
            "title": _("إدارة الرواتب وشؤون الموظفين"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("عقود الموظفين والرواتب"), "icon": "badge", "link": reverse_lazy("school_admin:payroll_employeecontract_changelist"), "permission": _school_check("payroll.view_employeecontract")},
                {"title": _("مسيرات الرواتب الشهرية"), "icon": "payments", "link": reverse_lazy("school_admin:payroll_payrollrun_changelist"), "permission": _school_check("payroll.view_payrollrun")},
                {"title": _("قسائم الرواتب"), "icon": "request_quote", "link": reverse_lazy("school_admin:payroll_payslip_changelist"), "permission": _school_check("payroll.view_payslip")},
                {"title": _("سلف وقروض الموظفين"), "icon": "credit_card", "link": reverse_lazy("school_admin:payroll_employeeloanadvance_changelist"), "permission": _school_check("payroll.view_employeeloanadvance")},
            ],
        },
        {
            "title": _("المشتريات والمستودعات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("الموردون المعتمدون"), "icon": "local_shipping", "link": reverse_lazy("school_admin:inventory_supplier_changelist"), "permission": _school_check("inventory.view_supplier")},
                {"title": _("المستودعات والمخازن"), "icon": "store", "link": reverse_lazy("school_admin:inventory_warehouse_changelist"), "permission": _school_check("inventory.view_warehouse")},
                {"title": _("دليل الأصناف والمواد"), "icon": "inventory", "link": reverse_lazy("school_admin:inventory_inventoryitem_changelist"), "permission": _school_check("inventory.view_inventoryitem")},
                {"title": _("سجل حركات المخزون"), "icon": "swap_horiz", "link": reverse_lazy("school_admin:inventory_stockmovement_changelist"), "permission": _school_check("inventory.view_stockmovement")},
                {"title": _("أوامر الشراء والتوريد"), "icon": "shopping_cart", "link": reverse_lazy("school_admin:inventory_purchaseorder_changelist"), "permission": _school_check("inventory.view_purchaseorder")},
            ],
        },
        {
            "title": _("الأصول الثابتة والإهلاك"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("سجل الأصول الثابتة"), "icon": "devices", "link": reverse_lazy("school_admin:assets_fixedasset_changelist"), "permission": _school_check("assets.view_fixedasset")},
                {"title": _("تصنيفات الأصول"), "icon": "category", "link": reverse_lazy("school_admin:assets_assetcategory_changelist"), "permission": _school_check("assets.view_assetcategory")},
                {"title": _("سجلات الإهلاك الدوري"), "icon": "trending_down", "link": reverse_lazy("school_admin:assets_assetdepreciationentry_changelist"), "permission": _school_check("assets.view_assetdepreciationentry")},
            ],
        },
        {
            "title": _("الخدمات المساندة (النقل والمكتبة والعيادة)"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("خطوط النقل المدرسي"), "icon": "directions_bus", "link": reverse_lazy("school_admin:school_services_busroute_changelist"), "permission": _school_check("school_services.view_busroute")},
                {"title": _("اشتراكات حافلات الطلاب"), "icon": "commute", "link": reverse_lazy("school_admin:school_services_studentbussubscription_changelist"), "permission": _school_check("school_services.view_studentbussubscription")},
                {"title": _("المحاسبة المالية للباصات والسائقين"), "icon": "account_balance_wallet", "link": reverse_lazy("school_admin:school_services_busfinancialsettlement_changelist"), "permission": _school_check("school_services.view_busfinancialsettlement")},
                {"title": _("أوامر صرف الكتب لمسؤول المخزن"), "icon": "local_shipping", "link": reverse_lazy("school_admin:school_services_bookrequisitionorder_changelist"), "permission": _school_check("school_services.view_bookrequisitionorder")},
                {"title": _("توزيع وتسليم الكتب المدرسية"), "icon": "auto_stories", "link": reverse_lazy("school_admin:school_services_studentbookdistribution_changelist"), "permission": _school_check("school_services.view_studentbookdistribution")},
                {"title": _("المكتبة والكتب"), "icon": "local_library", "link": reverse_lazy("school_admin:school_services_librarybook_changelist"), "permission": _school_check("school_services.view_librarybook")},
                {"title": _("إعارات الكتب"), "icon": "menu_book", "link": reverse_lazy("school_admin:school_services_bookloan_changelist"), "permission": _school_check("school_services.view_bookloan")},
                {"title": _("الملفات الصحية للطلاب"), "icon": "health_and_safety", "link": reverse_lazy("school_admin:school_services_studenthealthprofile_changelist"), "permission": _school_check("school_services.view_studenthealthprofile")},
                {"title": _("زيارات العيادة المدرسية"), "icon": "medical_services", "link": reverse_lazy("school_admin:school_services_clinicvisit_changelist"), "permission": _school_check("school_services.view_clinicvisit")},
            ],
        },
        {
            "title": _("الإشعارات والتنبيهات"), "separator": True, "collapsible": True,
            "items": [
                {"title": _("إشعارات المدرسة"), "icon": "notifications", "link": reverse_lazy("school_admin:notifications_notification_changelist"), "permission": _school_check("notifications.view_notification")},
                {"title": _("قوالب الإشعار"), "icon": "drafts", "link": reverse_lazy("school_admin:notifications_notificationtemplate_changelist"), "permission": _school_check("notifications.view_notificationtemplate")},
                {"title": _("تفضيلات الإشعار"), "icon": "notifications_active", "link": reverse_lazy("school_admin:notifications_notificationpreference_changelist"), "permission": _school_check("notifications.view_notificationpreference")},
                {"title": _("بوابات الواتساب والرسائل"), "icon": "chat", "link": reverse_lazy("school_admin:notifications_schoolmessaginggateway_changelist"), "permission": _school_check("notifications.view_notification")},
            ],
        },
    ]
