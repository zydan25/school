"""Tenant-safe API views for transportation, library, textbooks and clinic."""
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

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.academics.models import AcademicYear
from apps.inventory.models import InventoryItem, StockMovement
from apps.school_services.models import (
    BookLoan,
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusRoute,
    ClinicVisit,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
    StudentHealthProfile,
)
from apps.students.models import Student
from apps.staff.models import Teacher

from .serializers import (
    BookLoanSerializer,
    BookRequisitionOrderSerializer,
    BusFinancialSettlementSerializer,
    BusRouteSerializer,
    ClinicVisitSerializer,
    LibraryBookSerializer,
    StudentBookDistributionSerializer,
    StudentBusSubscriptionSerializer,
    StudentHealthProfileSerializer,
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
CLINIC_ROLES = ADMIN_ROLES | {
    "school-nurse", "school_nurse", "nurse", "school-doctor",
    "school_doctor", "doctor", "clinic", "clinic-staff", "clinic_staff",
    "health-officer", "health_officer",
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


def school_for(request):
    school = resolve_active_school(request)
    if not school:
        raise PermissionDenied("حدد المدرسة النشطة أولاً وتأكد من أن عضويتك سارية.")
    return school


class SchoolServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

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
        allowed = self.action_role_map.get(
            getattr(self, "action", ""),
            self.read_roles if getattr(self, "action", "") in {"list", "retrieve"} else self.write_roles,
        )
        require_school_role_or_permission(request, self.get_school(), allowed)

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


class BusRouteViewSet(SchoolServiceViewSet):
    serializer_class = BusRouteSerializer
    read_roles = TRANSPORT_READ_ROLES
    write_roles = TRANSPORT_ROLES
    action_role_map = {"list": TRANSPORT_READ_ROLES, "retrieve": TRANSPORT_READ_ROLES}

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "driver_user", "supervisor_teacher"
        )
        if not has_school_roles(self.request.user, self.get_school(), TRANSPORT_ROLES):
            queryset = queryset.filter(driver_user=self.request.user)
        return queryset.order_by("route_name")

    def perform_destroy(self, instance):
        active_subscriptions = instance.student_subscriptions.filter(
            status=StudentBusSubscription.Status.ACTIVE,
            is_archived=False,
        ).exists()
        if active_subscriptions:
            raise ValidationError("لا يمكن أرشفة خط نقل عليه اشتراكات نشطة.")
        super().perform_destroy(instance)

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
            serializer.save()


class StudentBusSubscriptionViewSet(SchoolServiceViewSet):
    serializer_class = StudentBusSubscriptionSerializer
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
            status_value = serializer.validated_data.get(
                "status", serializer.instance.status
            )
            if status_value == StudentBusSubscription.Status.ACTIVE:
                self._check_route_capacity(
                    route, exclude_subscription_id=serializer.instance.pk
                )
            self.save_serializer(serializer)


class LibraryBookViewSet(SchoolServiceViewSet):
    serializer_class = LibraryBookSerializer
    read_roles = LIBRARY_READ_ROLES
    write_roles = LIBRARY_ROLES
    action_role_map = {"list": LIBRARY_READ_ROLES, "retrieve": LIBRARY_READ_ROLES}

    def get_queryset(self):
        return super().get_queryset().order_by("title")


class BookLoanViewSet(SchoolServiceViewSet):
    serializer_class = BookLoanSerializer
    read_roles = LIBRARY_READ_ROLES
    write_roles = LIBRARY_ROLES
    action_role_map = {
        "list": LIBRARY_READ_ROLES,
        "retrieve": LIBRARY_READ_ROLES,
        "return_copy": LIBRARY_ROLES,
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
        with transaction.atomic():
            loan = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
            )
            if loan.status == BookLoan.Status.RETURNED:
                return Response(BookLoanSerializer(loan).data)
            if loan.status not in {BookLoan.Status.BORROWED, BookLoan.Status.OVERDUE}:
                raise ValidationError("لا يمكن إرجاع هذا السجل بحالته الحالية.")
            loan.status = BookLoan.Status.RETURNED
            loan.return_date = timezone.localdate()
            try:
                loan.save(update_fields=["status", "return_date", "updated_at"])
            except DjangoValidationError as exc:
                detail = getattr(exc, "message_dict", None) or exc.messages
                raise ValidationError(detail) from exc
        return Response(BookLoanSerializer(loan).data)


class BusFinancialSettlementViewSet(SchoolServiceViewSet):
    serializer_class = BusFinancialSettlementSerializer
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
                self.get_queryset().select_for_update(), pk=pk
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
                self.get_queryset().select_for_update(), pk=pk
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
                self.get_queryset().select_for_update(), pk=pk
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
                self.get_queryset().select_for_update(), pk=pk
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
                self.get_queryset().select_for_update(), pk=pk
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
            order.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="items")
    def add_items(self, request, pk=None):
        items_data = request.data.get("items")
        if not isinstance(items_data, list) or not items_data:
            raise ValidationError({"items": "أرسل قائمة بنود غير فارغة."})
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
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
                self.get_queryset().select_for_update(), pk=pk
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
                item.save(update_fields=["quantity_approved", "updated_at"])
            order.status = BookRequisitionOrder.Status.APPROVED
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
            )
            if order.status != BookRequisitionOrder.Status.SUBMITTED:
                raise ValidationError("لا يرفض إلا الطلب المرفوع.")
            reason = str(request.data.get("reason", "")).strip()
            if reason:
                order.notes = (order.notes + "\nسبب الرفض: " + reason).strip()
            order.status = BookRequisitionOrder.Status.REJECTED
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.save(update_fields=["status", "approved_by", "approved_at", "notes", "updated_at"])
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def fulfill(self, request, pk=None):
        allocations = request.data.get("items")
        if not isinstance(allocations, list) or not allocations:
            raise ValidationError({
                "items": "أرسل قائمة البنود مع inventory_item_id وquantity لكل بند."
            })
        used_item_ids = set()
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
            )
            if order.status != BookRequisitionOrder.Status.APPROVED:
                raise ValidationError("لا يصرف إلا أمر الصرف المعتمد.")
            requisition_items = {
                str(item.pk): item
                for item in order.items.select_for_update()
            }
            for allocation in allocations:
                requisition_item_id = str(allocation.get("requisition_item_id", ""))
                if requisition_item_id in used_item_ids:
                    raise ValidationError("لا تكرر بنداً في طلب الصرف.")
                used_item_ids.add(requisition_item_id)
                req_item = requisition_items.get(requisition_item_id)
                if req_item is None:
                    raise ValidationError("أحد البنود لا يتبع أمر الصرف الحالي.")
                try:
                    quantity = Decimal(str(allocation.get("quantity", "0")))
                except Exception as exc:
                    raise ValidationError("كمية الصرف غير صالحة.") from exc
                remaining = req_item.quantity_approved - req_item.quantity_dispatched
                if quantity <= 0 or quantity != quantity.to_integral_value() or quantity > remaining:
                    raise ValidationError("كمية الصرف يجب أن تكون عدداً صحيحاً موجباً ولا تتجاوز الكمية المعتمدة المتبقية.")
                inventory_item = get_object_or_404(
                    InventoryItem.objects.select_for_update(),
                    pk=allocation.get("inventory_item_id"),
                    school=self.get_school(),
                    is_archived=False,
                )
                try:
                    StockMovement.objects.create(
                        school=self.get_school(),
                        item=inventory_item,
                        movement_type=StockMovement.MovementType.ISSUE,
                        quantity=quantity,
                        unit_cost=inventory_item.unit_cost,
                        recipient_name=f"أمر صرف الكتب {order.order_number}",
                        reference=order.order_number,
                        notes=f"{req_item.book_title} - صرف لصالح الطلب",
                    )
                except DjangoValidationError as exc:
                    raise ValidationError(
                        getattr(exc, "message_dict", None) or exc.messages
                    ) from exc
                req_item.quantity_dispatched += int(quantity)
                req_item.save(update_fields=["quantity_dispatched", "updated_at"])
            if all(
                item.quantity_dispatched >= item.quantity_approved
                for item in requisition_items.values()
            ):
                order.status = BookRequisitionOrder.Status.FULFILLED
                order.fulfilled_by = request.user
                order.fulfilled_at = timezone.now()
                order.save(update_fields=["status", "fulfilled_by", "fulfilled_at", "updated_at"])
        order.refresh_from_db()
        return Response(self.get_serializer(order).data)


class StudentHealthProfileViewSet(SchoolServiceViewSet):
    serializer_class = StudentHealthProfileSerializer
    read_roles = CLINIC_ROLES
    write_roles = CLINIC_ROLES
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().select_related("student").order_by("student__first_name")


class ClinicVisitViewSet(SchoolServiceViewSet):
    serializer_class = ClinicVisitSerializer
    read_roles = CLINIC_ROLES
    write_roles = CLINIC_ROLES
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("student").order_by("-visit_date")
        student_id = self.request.query_params.get("student")
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return queryset
