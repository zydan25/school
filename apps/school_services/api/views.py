"""Tenant-safe API views for optional transportation, library, and textbook services."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditlog.services import record_event
from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounts.services import is_platform_operator
from apps.school_services.models import (
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusRoute,
    BusSubscriptionCharge,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
)
from apps.staff.models import Teacher

from apps.school_services.services import (
    fulfill_book_requisition,
    issue_bus_route_monthly_invoices,
    mark_book_loan_lost,
    renew_book_loan,
    return_book_loan,
    school_service_feature_state,
    update_library_policy,
    school_service_is_enabled,
    set_school_service_enabled,
)

from .serializers import (
    BookLoanSerializer,
    BookRequisitionOrderSerializer,
    BusFinancialSettlementSerializer,
    BusRouteSerializer,
    BusSubscriptionChargeSerializer,
    LibraryBookSerializer,
    StudentBookDistributionSerializer,
    StudentBusSubscriptionSerializer,
)


ADMIN_ROLES = {
    "admin", "school-admin", "school_admin", "school-director",
    "school_director", "principal", "school-principal",
    "student-affairs", "student_affairs",
}
TRANSPORT_ROLES = ADMIN_ROLES | {
    "transport-manager", "transport_manager", "transport-officer",
    "transport_officer", "bus-supervisor", "bus_supervisor",
}
LIBRARY_ROLES = ADMIN_ROLES | {
    "librarian", "library-manager", "library_manager",
}
INVENTORY_ROLES = ADMIN_ROLES | {
    "store-keeper", "store_keeper", "inventory-manager", "inventory_manager",
}
ACADEMIC_ROLES = ADMIN_ROLES | {
    "academic-coordinator", "academic_coordinator", "academic-head",
    "academic_head", "exam-controller", "exam_controller",
}
TEACHER_ROLES = {"teacher"}
FAMILY_READ_ROLES = {"guardian", "student"}
LIBRARY_READ_ROLES = LIBRARY_ROLES | TEACHER_ROLES | FAMILY_READ_ROLES
TRANSPORT_READ_ROLES = TRANSPORT_ROLES | {"bus-driver", "bus_driver"}
DISTRIBUTION_READ_ROLES = ADMIN_ROLES | INVENTORY_ROLES | ACADEMIC_ROLES | FAMILY_READ_ROLES
REQUISITION_READ_ROLES = ADMIN_ROLES | INVENTORY_ROLES | ACADEMIC_ROLES | TEACHER_ROLES
BUS_BILLING_ROLES = ADMIN_ROLES | FINANCIAL_ROLES


def school_for(request):
    school = resolve_active_school(request)
    if not school:
        raise PermissionDenied("حدد المدرسة النشطة أولاً وتأكد من أن عضويتك سارية.")
    return school


class SchoolServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_feature_code = ""
    action_permission_map = {}

    def save_serializer(self, serializer, **kwargs):
        try:
            return serializer.save(**kwargs)
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
    read_roles = ADMIN_ROLES
    write_roles = ADMIN_ROLES
    action_role_map = {}

    def get_school(self):
        if not hasattr(self, "_active_school"):
            self._active_school = school_for(self.request)
        return self._active_school

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = self.get_school()
        action = getattr(self, "action", "")
        if (
            self.required_feature_code
            and not is_platform_operator(request.user)
            and not school_service_is_enabled(school, self.required_feature_code)
        ):
            raise PermissionDenied({
                "detail": "هذه الخدمة غير متاحة أو معطلة لهذه المدرسة.",
                "code": "feature_disabled",
                "feature": self.required_feature_code,
                "school": school.code,
            })
        allowed = self.action_role_map.get(
            action,
            self.read_roles if action in {"list", "retrieve"} else self.write_roles,
        )
        permission = self.action_permission_map.get(action)
        if permission is None:
            permission_prefix = {
                "list": "view", "retrieve": "view", "create": "add",
                "update": "change", "partial_update": "change", "destroy": "delete",
            }.get(action)
            if permission_prefix:
                model = self.get_serializer_class().Meta.model
                permission = f"{model._meta.app_label}.{permission_prefix}_{model._meta.model_name}"
        elif "." not in permission:
            permission = f"school_services.{permission}"
        require_school_role_or_permission(
            request, school, allowed, permission_codename=permission
        )

    def get_queryset(self):
        model = self.get_serializer_class().Meta.model
        queryset = model.objects.filter(school=self.get_school(), is_archived=False)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = self.get_school()
        return context

    def perform_create(self, serializer):
        self.save_serializer(serializer, school=self.get_school())

    def perform_update(self, serializer):
        self.save_serializer(serializer)

    def perform_destroy(self, instance):
        if not hasattr(instance, "archive"):
            raise MethodNotAllowed("DELETE")
        try:
            instance.archive(actor=self.request.user, reason="أرشفة عبر واجهة خدمات المدرسة")
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc


class SchoolServiceFeaturesView(APIView):
    """Read service entitlements and allow school administrators to disable/restore them."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = school_for(request)
        require_school_role_or_permission(
            request, school,
            ADMIN_ROLES | TRANSPORT_ROLES | LIBRARY_ROLES | INVENTORY_ROLES | ACADEMIC_ROLES,
        )
        return Response({"features": school_service_feature_state(school)})

    def patch(self, request):
        school = school_for(request)
        require_school_role_or_permission(request, school, ADMIN_ROLES)
        code = str(request.data.get("code", "")).strip()
        enabled = request.data.get("enabled")
        try:
            result = set_school_service_enabled(
                school=school, feature_code=code, enabled=enabled, actor=request.user
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        return Response(result)


class LibraryPolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def _school(self, request):
        school = school_for(request)
        if (
            not is_platform_operator(request.user)
            and not school_service_is_enabled(school, "school-library")
        ):
            raise PermissionDenied({
                "detail": "خدمة المكتبة غير مفعلة لهذه المدرسة.",
                "code": "feature_disabled",
                "feature": "school-library",
                "school": school.code,
            })
        return school

    @staticmethod
    def _data(settings):
        return {
            "library_default_loan_days": settings.library_default_loan_days,
            "library_max_renewals": settings.library_max_renewals,
            "library_overdue_fine_per_day": str(settings.library_overdue_fine_per_day),
            "library_max_overdue_fine": str(settings.library_max_overdue_fine),
            "library_lost_book_fine": str(settings.library_lost_book_fine),
        }

    def get(self, request):
        school = self._school(request)
        require_school_role_or_permission(
            request, school, LIBRARY_ROLES,
            permission_codename="school_services.manage_library_policy",
        )
        from apps.tenants.models import SchoolSettings
        settings = SchoolSettings.objects.filter(school=school).first()
        if settings is None:
            settings = SchoolSettings(school=school)
        return Response(self._data(settings))

    def patch(self, request):
        school = self._school(request)
        require_school_role_or_permission(
            request, school, LIBRARY_ROLES,
            permission_codename="school_services.manage_library_policy",
        )
        try:
            settings = update_library_policy(
                school=school, values=request.data, actor=request.user
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        return Response(self._data(settings))


class BusRouteViewSet(SchoolServiceViewSet):
    serializer_class = BusRouteSerializer
    required_feature_code = "school-transport"
    action_permission_map = {"bill_month": "bill_studentbussubscription"}
    read_roles = TRANSPORT_READ_ROLES
    write_roles = TRANSPORT_ROLES
    action_role_map = {
        "list": TRANSPORT_READ_ROLES,
        "retrieve": TRANSPORT_READ_ROLES,
        "bill_month": BUS_BILLING_ROLES,
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "driver_user", "supervisor_teacher"
        )
        if not has_school_roles(self.request.user, self.get_school(), TRANSPORT_ROLES):
            queryset = queryset.filter(driver_user=self.request.user)
        return queryset.order_by("route_name")

    def perform_destroy(self, instance):
        with transaction.atomic():
            route = get_object_or_404(
                BusRoute.objects.select_for_update(),
                pk=instance.pk,
                school=self.get_school(),
                is_archived=False,
            )
            active_subscriptions = route.student_subscriptions.filter(
                status=StudentBusSubscription.Status.ACTIVE,
                is_archived=False,
            ).exists()
            if active_subscriptions:
                raise ValidationError("لا يمكن أرشفة خط نقل عليه اشتراكات نشطة.")
            super().perform_destroy(route)
            record_event(
                action="school_transport.route.archived",
                description=f"أرشفة خط النقل {route.route_code}",
                actor=self.request.user,
                school=self.get_school(),
                obj=route,
                request=self.request,
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            route = get_object_or_404(
                BusRoute.objects.select_for_update(),
                pk=serializer.instance.pk,
                school=self.get_school(),
                is_archived=False,
            )
            capacity = serializer.validated_data.get("bus_capacity", route.bus_capacity)
            active_count = route.student_subscriptions.filter(
                status=StudentBusSubscription.Status.ACTIVE,
                is_archived=False,
            ).count()
            if capacity < active_count:
                raise ValidationError(
                    "لا يمكن خفض سعة الحافلة عن عدد اشتراكاتها النشطة."
                )
            serializer.instance = route
            self.save_serializer(serializer)

    @action(detail=True, methods=["post"], url_path="bill-month")
    def bill_month(self, request, pk=None):
        year = request.data.get("year")
        month = request.data.get("month")
        try:
            result = issue_bus_route_monthly_invoices(
                school=self.get_school(), route_id=pk, year=year, month=month,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        return Response({
            "created": result["created"],
            "already_issued": result["already_issued"],
            "charges": BusSubscriptionChargeSerializer(result["charges"], many=True).data,
        })


class StudentBusSubscriptionViewSet(SchoolServiceViewSet):
    serializer_class = StudentBusSubscriptionSerializer
    required_feature_code = "school-transport"
    read_roles = TRANSPORT_ROLES | FAMILY_READ_ROLES
    write_roles = TRANSPORT_ROLES
    action_role_map = {"list": read_roles, "retrieve": read_roles}

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "student", "bus_route", "academic_year"
        )
        if has_school_roles(self.request.user, self.get_school(), TRANSPORT_ROLES):
            return queryset.order_by("-created_at")
        if has_school_roles(self.request.user, self.get_school(), {"student"}):
            queryset = queryset.filter(student__user=self.request.user)
        else:
            queryset = queryset.filter(
                student__guardians__guardian__user=self.request.user,
                student__guardians__is_archived=False,
                student__guardians__guardian__is_archived=False,
            )
        return queryset.distinct().order_by("-created_at")

    def _check_route_capacity(self, route, *, exclude_subscription_id=None):
        if not route.is_active:
            raise ValidationError({"bus_route": "خط النقل غير نشط ولا يقبل اشتراكات جديدة."})
        active = route.student_subscriptions.filter(
            status=StudentBusSubscription.Status.ACTIVE,
            is_archived=False,
        )
        if exclude_subscription_id:
            active = active.exclude(pk=exclude_subscription_id)
        if active.count() >= route.bus_capacity:
            raise ValidationError({"bus_route": "اكتملت سعة الحافلة لهذا الخط."})

    def perform_create(self, serializer):
        with transaction.atomic():
            route = get_object_or_404(
                BusRoute.objects.select_for_update(),
                pk=serializer.validated_data["bus_route"].pk,
                school=self.get_school(),
                is_archived=False,
            )
            status_value = serializer.validated_data.get(
                "status", StudentBusSubscription.Status.ACTIVE
            )
            if status_value == StudentBusSubscription.Status.ACTIVE:
                self._check_route_capacity(route)
            self.save_serializer(serializer, school=self.get_school())

    def perform_update(self, serializer):
        with transaction.atomic():
            route_id = serializer.validated_data.get(
                "bus_route", serializer.instance.bus_route
            ).pk
            route = get_object_or_404(
                BusRoute.objects.select_for_update(),
                pk=route_id,
                school=self.get_school(),
                is_archived=False,
            )
            subscription = get_object_or_404(
                StudentBusSubscription.objects.select_for_update(),
                pk=serializer.instance.pk,
                school=self.get_school(),
                is_archived=False,
            )
            status_value = serializer.validated_data.get(
                "status", subscription.status
            )
            if status_value == StudentBusSubscription.Status.ACTIVE:
                self._check_route_capacity(
                    route, exclude_subscription_id=subscription.pk
                )
            serializer.instance = subscription
            self.save_serializer(serializer)


    def perform_destroy(self, instance):
        # Deleting a transport subscription means cancelling it, never erasing
        # its billing and route history.
        with transaction.atomic():
            get_object_or_404(
                BusRoute.objects.select_for_update(),
                pk=instance.bus_route_id,
                school=self.get_school(),
            )
            subscription = get_object_or_404(
                StudentBusSubscription.objects.select_for_update(),
                pk=instance.pk,
                school=self.get_school(),
                is_archived=False,
            )
            if subscription.status != StudentBusSubscription.Status.CANCELLED:
                subscription.status = StudentBusSubscription.Status.CANCELLED
                subscription.save(update_fields=["status", "updated_at"])
                record_event(
                    action="school_transport.subscription.cancelled",
                    description="إلغاء اشتراك نقل طالب",
                    actor=self.request.user,
                    school=self.get_school(),
                    obj=subscription,
                    request=self.request,
                )


class LibraryBookViewSet(SchoolServiceViewSet):
    serializer_class = LibraryBookSerializer
    required_feature_code = "school-library"
    read_roles = LIBRARY_READ_ROLES
    write_roles = LIBRARY_ROLES
    action_role_map = {"list": LIBRARY_READ_ROLES, "retrieve": LIBRARY_READ_ROLES}

    def get_queryset(self):
        return super().get_queryset().order_by("title")

    def perform_update(self, serializer):
        with transaction.atomic():
            book = get_object_or_404(
                LibraryBook.objects.select_for_update(),
                pk=serializer.instance.pk,
                school=self.get_school(),
                is_archived=False,
            )
            serializer.instance = book
            self.save_serializer(serializer)


class BookLoanViewSet(SchoolServiceViewSet):
    serializer_class = BookLoanSerializer
    required_feature_code = "school-library"
    action_permission_map = {
        "return_copy": "return_bookloan",
        "renew": "renew_bookloan",
        "mark_lost": "marklost_bookloan",
    }
    read_roles = LIBRARY_READ_ROLES
    write_roles = LIBRARY_ROLES
    action_role_map = {
        "list": LIBRARY_READ_ROLES,
        "retrieve": LIBRARY_READ_ROLES,
        "return_copy": LIBRARY_ROLES,
        "renew": LIBRARY_ROLES,
        "mark_lost": LIBRARY_ROLES,
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "book", "student", "teacher"
        )
        if has_school_roles(self.request.user, self.get_school(), LIBRARY_ROLES):
            return queryset.order_by("-borrow_date")
        personal = queryset.none()
        if has_school_roles(self.request.user, self.get_school(), {"student"}):
            personal = queryset.filter(student__user=self.request.user)
        elif has_school_roles(self.request.user, self.get_school(), {"teacher"}):
            personal = queryset.filter(teacher__user=self.request.user)
        elif has_school_roles(self.request.user, self.get_school(), {"guardian"}):
            personal = queryset.filter(
                student__guardians__guardian__user=self.request.user,
                student__guardians__is_archived=False,
                student__guardians__guardian__is_archived=False,
            )
        return personal.distinct().order_by("-borrow_date")

    def perform_create(self, serializer):
        self.save_serializer(serializer, school=self.get_school())

    @action(detail=True, methods=["post"], url_path="return")
    def return_copy(self, request, pk=None):
        try:
            loan = return_book_loan(
                school=self.get_school(), loan_id=pk, actor=request.user
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        return Response(BookLoanSerializer(loan).data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        try:
            loan = renew_book_loan(
                school=self.get_school(), loan_id=pk, actor=request.user
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        return Response(BookLoanSerializer(loan).data)

    @action(detail=True, methods=["post"], url_path="mark-lost")
    def mark_lost(self, request, pk=None):
        try:
            loan = mark_book_loan_lost(
                school=self.get_school(), loan_id=pk, actor=request.user
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        return Response(BookLoanSerializer(loan).data)


class BusSubscriptionChargeViewSet(SchoolServiceViewSet):
    serializer_class = BusSubscriptionChargeSerializer
    required_feature_code = "school-transport"
    read_roles = TRANSPORT_ROLES | FINANCIAL_ROLES
    write_roles = set()
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        queryset = BusSubscriptionCharge.objects.filter(
            school=self.get_school(), is_archived=False
        ).select_related("subscription", "subscription__student", "invoice")
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        route_id = self.request.query_params.get("route")
        if year:
            queryset = queryset.filter(billing_year=year)
        if month:
            queryset = queryset.filter(billing_month=month)
        if route_id:
            queryset = queryset.filter(subscription__bus_route_id=route_id)
        return queryset.order_by("-billing_year", "-billing_month", "-created_at")


class BusFinancialSettlementViewSet(SchoolServiceViewSet):
    serializer_class = BusFinancialSettlementSerializer
    required_feature_code = "school-transport"
    action_permission_map = {
        "calculate": "calculate_busfinancialsettlement",
        "approve": "approve_busfinancialsettlement",
    }
    read_roles = FINANCIAL_ROLES | ADMIN_ROLES
    write_roles = FINANCIAL_ROLES | ADMIN_ROLES
    action_role_map = {
        "list": read_roles,
        "retrieve": read_roles,
        "calculate": write_roles,
        "approve": write_roles,
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().select_related(
            "bus_route", "academic_year", "payment_voucher"
        ).order_by("-year", "-month")

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        with transaction.atomic():
            settlement = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if settlement.status != BusFinancialSettlement.Status.DRAFT:
                raise ValidationError("لا يعاد احتساب التسوية بعد اعتمادها.")
            settlement.calculate_due()
            try:
                settlement.save()
            except DjangoValidationError as exc:
                detail = getattr(exc, "message_dict", None) or exc.messages
                raise ValidationError(detail) from exc
        return Response(self.get_serializer(settlement).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        with transaction.atomic():
            settlement = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if settlement.status == BusFinancialSettlement.Status.PAID:
                raise ValidationError("التسوية مصروفة بالفعل ولا يمكن إعادة اعتمادها.")
            try:
                settlement.approve_and_create_payment_voucher(
                    approved_by_user=request.user
                )
            except DjangoValidationError as exc:
                raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
            settlement.refresh_from_db()
            if settlement.net_payable > Decimal("0.00") and not settlement.payment_voucher_id:
                raise ValidationError(
                    "تعذر إنشاء سند الصرف؛ تحقق من إعداد حساب مصروفات النقل وحساب الصندوق."
                )
        return Response(self.get_serializer(settlement).data)


class StudentBookDistributionViewSet(SchoolServiceViewSet):
    serializer_class = StudentBookDistributionSerializer
    required_feature_code = "school-book-distribution"
    action_permission_map = {
        "deliver": "deliver_studentbookdistribution",
        "return_copy": "return_studentbookdistribution",
    }
    read_roles = DISTRIBUTION_READ_ROLES
    write_roles = ADMIN_ROLES | INVENTORY_ROLES | ACADEMIC_ROLES
    action_role_map = {
        "list": DISTRIBUTION_READ_ROLES,
        "retrieve": DISTRIBUTION_READ_ROLES,
        "deliver": ADMIN_ROLES | INVENTORY_ROLES,
        "return_copy": ADMIN_ROLES | INVENTORY_ROLES,
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "student", "academic_year", "inventory_item", "invoice"
        )
        if has_school_roles(self.request.user, self.get_school(), ADMIN_ROLES | INVENTORY_ROLES | ACADEMIC_ROLES):
            return queryset.order_by("-created_at")
        if has_school_roles(self.request.user, self.get_school(), {"student"}):
            return queryset.filter(student__user=self.request.user).order_by("-created_at")
        return queryset.filter(
            student__guardians__guardian__user=self.request.user,
            student__guardians__is_archived=False,
            student__guardians__guardian__is_archived=False,
        ).distinct().order_by("-created_at")

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        with transaction.atomic():
            distribution = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            try:
                distribution.deliver_book(user=request.user)
            except DjangoValidationError as exc:
                raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
            distribution.refresh_from_db()
        return Response(self.get_serializer(distribution).data)

    @action(detail=True, methods=["post"], url_path="return")
    def return_copy(self, request, pk=None):
        with transaction.atomic():
            distribution = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if distribution.delivery_status != StudentBookDistribution.DeliveryStatus.DELIVERED:
                raise ValidationError("لا يمكن استرجاع كتاب لم يتم تسليمه.")
            try:
                distribution.return_book(user=request.user)
            except DjangoValidationError as exc:
                raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
            distribution.refresh_from_db()
        return Response(self.get_serializer(distribution).data)


class BookRequisitionOrderViewSet(SchoolServiceViewSet):
    serializer_class = BookRequisitionOrderSerializer
    required_feature_code = "school-book-distribution"
    action_permission_map = {
        "submit": "submit_bookrequisitionorder",
        "add_items": "submit_bookrequisitionorder",
        "approve": "approve_bookrequisitionorder",
        "reject": "reject_bookrequisitionorder",
        "fulfill": "fulfill_bookrequisitionorder",
    }
    read_roles = REQUISITION_READ_ROLES
    write_roles = ACADEMIC_ROLES | TEACHER_ROLES
    action_role_map = {
        "list": REQUISITION_READ_ROLES,
        "retrieve": REQUISITION_READ_ROLES,
        "submit": ACADEMIC_ROLES | TEACHER_ROLES,
        "add_items": ACADEMIC_ROLES | TEACHER_ROLES,
        "approve": ACADEMIC_ROLES,
        "reject": ACADEMIC_ROLES,
        "fulfill": INVENTORY_ROLES,
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("items").select_related(
            "academic_year", "grade_level", "section", "requested_by"
        )
        if has_school_roles(self.request.user, self.get_school(), ADMIN_ROLES | ACADEMIC_ROLES):
            return queryset.order_by("-created_at")
        if has_school_roles(self.request.user, self.get_school(), INVENTORY_ROLES):
            return queryset.filter(
                status__in=[
                    BookRequisitionOrder.Status.APPROVED,
                    BookRequisitionOrder.Status.FULFILLED,
                ]
            ).order_by("-created_at")
        return queryset.filter(requested_by=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        school = self.get_school()
        if (
            has_school_roles(self.request.user, school, TEACHER_ROLES)
            and not has_school_roles(self.request.user, school, ACADEMIC_ROLES)
        ):
            teacher = Teacher.objects.filter(
                school=school, user=self.request.user, is_archived=False
            ).first()
            if teacher is None:
                raise PermissionDenied("لا يوجد ملف معلم مرتبط بحسابك في هذه المدرسة.")
            year = serializer.validated_data["academic_year"]
            section = serializer.validated_data.get("section")
            grade = serializer.validated_data.get("grade_level")
            assignments = teacher.assignments.filter(
                school=school, academic_year=year, is_archived=False
            )
            if section is not None:
                assignments = assignments.filter(section=section)
            elif grade is not None:
                assignments = assignments.filter(section__grade=grade)
            else:
                raise PermissionDenied(
                    "حدد الصف أو الشعبة التي لديك إسناد تدريسي فيها عند إنشاء أمر الصرف."
                )
            if not assignments.exists():
                raise PermissionDenied(
                    "لا يمكنك إنشاء أمر صرف لصف أو شعبة غير مسندة إليك."
                )
        self.save_serializer(
            serializer,
            school=school,
            requested_by=self.request.user,
            status=BookRequisitionOrder.Status.DRAFT,
            order_number=f"REQ-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        )

    def perform_destroy(self, instance):
        raise MethodNotAllowed("DELETE", detail="أوامر الصرف تحفظ كسجل تدقيقي ولا تحذف.")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if order.requested_by_id != request.user.id and not has_school_roles(
                request.user, self.get_school(), ACADEMIC_ROLES
            ):
                raise PermissionDenied("لا يمكنك رفع أمر صرف أنشأه مستخدم آخر.")
            if order.status != BookRequisitionOrder.Status.DRAFT:
                raise ValidationError("لا يمكن رفع الطلب إلا من حالة المسودة.")
            if not order.items.exists():
                raise ValidationError("أضف بنداً واحداً على الأقل قبل رفع الطلب.")
            order.status = BookRequisitionOrder.Status.SUBMITTED
            order._allow_requisition_workflow_update = True
            order.save(update_fields=["status", "updated_at"])
            record_event(
                action="school_book_requisition.submitted",
                description=f"رفع أمر صرف الكتب {order.order_number}",
                actor=request.user,
                school=self.get_school(),
                obj=order,
                request=request,
            )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="items")
    def add_items(self, request, pk=None):
        items_data = request.data.get("items")
        if not isinstance(items_data, list) or not items_data:
            raise ValidationError({"items": "أرسل قائمة بنود غير فارغة."})
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if order.requested_by_id != request.user.id and not has_school_roles(
                request.user, self.get_school(), ACADEMIC_ROLES
            ):
                raise PermissionDenied("لا يمكنك تعديل طلب مستخدم آخر.")
            if order.status != BookRequisitionOrder.Status.DRAFT:
                raise ValidationError("لا يمكن تعديل البنود بعد رفع الطلب.")
            # Validate each row with the same declared item contract.
            from .serializers import BookRequisitionItemSerializer
            for payload in items_data:
                item_serializer = BookRequisitionItemSerializer(data=payload)
                item_serializer.is_valid(raise_exception=True)
                BookRequisitionItem.objects.create(
                    school=self.get_school(),
                    requisition=order,
                    **item_serializer.validated_data,
                )
        order.refresh_from_db()
        return Response(self.get_serializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if order.status != BookRequisitionOrder.Status.SUBMITTED:
                raise ValidationError("لا يعتمد إلا الطلب المرفوع.")
            overrides = request.data.get("items")
            if overrides is not None and not isinstance(overrides, list):
                raise ValidationError({"items": "يجب إرسال قائمة كميات الاعتماد."})
            approved_by_id = {}
            for entry in overrides or []:
                item_id = str(entry.get("id", ""))
                if item_id in approved_by_id:
                    raise ValidationError("لا تكرر بنداً في كميات الاعتماد.")
                approved_by_id[item_id] = entry.get("quantity_approved")
            unknown_item_ids = set(approved_by_id) - {str(item.pk) for item in order.items.all()}
            if unknown_item_ids:
                raise ValidationError("تتضمن كميات الاعتماد بنداً لا يتبع أمر الصرف الحالي.")
            for item in order.items.select_for_update():
                quantity = approved_by_id.get(str(item.pk), item.quantity_requested)
                if quantity is None or isinstance(quantity, bool) or not isinstance(quantity, int):
                    raise ValidationError("كمية الاعتماد يجب أن تكون عدداً صحيحاً.")
                if quantity < 0 or quantity > item.quantity_requested:
                    raise ValidationError("كمية الاعتماد يجب أن تكون بين صفر والكمية المطلوبة.")
                item.quantity_approved = quantity
                item._allow_requisition_approval_update = True
                item.save(update_fields=["quantity_approved", "updated_at"])
            order.status = BookRequisitionOrder.Status.APPROVED
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order._allow_requisition_workflow_update = True
            order.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
            record_event(
                action="school_book_requisition.approved",
                description=f"اعتماد أمر صرف الكتب {order.order_number}",
                actor=request.user,
                school=self.get_school(),
                obj=order,
                request=request,
                metadata={"approved_items": len(approved_by_id)},
            )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(of=("self",)), pk=pk
            )
            if order.status != BookRequisitionOrder.Status.SUBMITTED:
                raise ValidationError("لا يرفض إلا الطلب المرفوع.")
            reason = str(request.data.get("reason", "")).strip()
            if reason:
                order.notes = (order.notes + "\nسبب الرفض: " + reason).strip()
            order.status = BookRequisitionOrder.Status.REJECTED
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order._allow_requisition_workflow_update = True
            order.save(update_fields=["status", "approved_by", "approved_at", "notes", "updated_at"])
            record_event(
                action="school_book_requisition.rejected",
                description=f"رفض أمر صرف الكتب {order.order_number}",
                actor=request.user,
                school=self.get_school(),
                obj=order,
                request=request,
                metadata={"reason": reason},
            )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def fulfill(self, request, pk=None):
        allocations = request.data.get("items")
        if not isinstance(allocations, list) or not allocations:
            raise ValidationError({
                "items": "أرسل قائمة البنود مع inventory_item_id وquantity لكل بند."
            })
        try:
            order = fulfill_book_requisition(
                school=self.get_school(),
                order_id=pk,
                allocations=allocations,
                idempotency_key=request.headers.get("Idempotency-Key", ""),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(detail) from exc
        record_event(
            action="school_book_requisition.fulfilled",
            description=f"تنفيذ دفعة صرف لأمر الكتب {order.order_number}",
            actor=request.user,
            school=self.get_school(),
            obj=order,
            request=request,
            metadata={"idempotency_key": request.headers.get("Idempotency-Key", "")},
        )
        return Response(self.get_serializer(order).data)
