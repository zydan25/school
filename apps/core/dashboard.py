from django.db import DatabaseError


def dashboard_callback(request, context):
    """Separate central and school dashboards while sharing the Unfold shell."""
    if request.path.startswith("/school-admin/"):
        school = getattr(request, "school", None)
        metrics = {"academic_years": 0, "branches": 0, "sections": 0, "members": 0}
        if school is not None:
            try:
                from apps.academics.models import AcademicYear, Section
                from apps.accounts.models import SchoolMembership
                from apps.tenants.models import Branch
                metrics["academic_years"] = AcademicYear.objects.filter(school=school, is_archived=False).count()
                metrics["branches"] = Branch.objects.filter(school=school, is_archived=False).count()
                metrics["sections"] = Section.objects.filter(school=school, is_archived=False).count()
                metrics["members"] = SchoolMembership.objects.filter(school=school, status=SchoolMembership.Status.ACTIVE).count()
            except DatabaseError:
                metrics["database_unavailable"] = True
        context.update({"school_metrics": metrics, "dashboard_title": "لوحة المدرسة", "dashboard_subtitle": school.name if school else "اختر مدرسة للمتابعة"})
        return context

    from apps.accounts.models import SchoolMembership, User
    from apps.platform.models import Subscription
    from apps.tenants.models import School
    metrics = {"schools": 0, "active_schools": 0, "users": 0, "memberships": 0, "subscriptions": 0}
    try:
        metrics["schools"] = School.objects.count()
        metrics["active_schools"] = School.objects.filter(status=School.Status.ACTIVE).count()
        metrics["users"] = User.objects.count()
        metrics["memberships"] = SchoolMembership.objects.filter(status=SchoolMembership.Status.ACTIVE).count()
        metrics["subscriptions"] = Subscription.objects.filter(status=Subscription.Status.ACTIVE).count()
    except DatabaseError:
        metrics["database_unavailable"] = True
    context.update({"platform_metrics": metrics, "dashboard_title": "نظرة عامة على المنصة", "dashboard_subtitle": "مؤشرات تشغيلية للمدارس والمستخدمين والاشتراكات"})
    return context
