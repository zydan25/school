"""Serializers for the school support-services API."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import SchoolMembership
from apps.tenants.models import SchoolSettings
from apps.school_services.models import (
    BookLoan,
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusSubscriptionCharge,
    BusRoute,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
)


class SchoolServiceSerializer(serializers.ModelSerializer):
    """Tenant-safe serializer shared by school-service resources."""

    class Meta:
        fields = "__all__"
        read_only_fields = (
            "id", "school", "branch", "created_at", "updated_at",
            "is_archived", "archived_at", "archived_by",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        if not school:
            return attrs

        model = self.Meta.model
        for model_field in model._meta.fields:
            if not model_field.is_relation or not (
                model_field.many_to_one or model_field.one_to_one
            ):
                continue
            name = model_field.name
            related = attrs.get(name)
            if related is None and self.instance is not None:
                related = getattr(self.instance, name, None)
            related_school_id = getattr(related, "school_id", None) if related else None
            if related_school_id and str(related_school_id) != str(school.pk):
                raise serializers.ValidationError({
                    name: "العنصر المرتبط لا يتبع المدرسة النشطة."
                })

        driver_user = attrs.get("driver_user")
        if driver_user is None and self.instance is not None:
            driver_user = self.instance.driver_user
        if driver_user is not None and not SchoolMembership.objects.filter(
            user=driver_user,
            school=school,
            status=SchoolMembership.Status.ACTIVE,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).exists():
            raise serializers.ValidationError({
                "driver_user": "يجب أن يمتلك حساب السائق عضوية نشطة في المدرسة."
            })
        return attrs


class BusSubscriptionChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusSubscriptionCharge
        fields = (
            "id", "subscription", "invoice", "billing_year", "billing_month",
            "amount", "issued_by", "created_at",
        )
        read_only_fields = fields


class BusRouteSerializer(SchoolServiceSerializer):
    bus_capacity = serializers.IntegerField(min_value=1)
    monthly_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.00")
    )
    contract_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.00")
    )

    class Meta(SchoolServiceSerializer.Meta):
        model = BusRoute
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields


class StudentBusSubscriptionSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = StudentBusSubscription
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context.get("school")
        student = attrs.get("student", getattr(self.instance, "student", None))
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        if school and student and year:
            existing = StudentBusSubscription.objects.filter(
                school=school,
                student=student,
                academic_year=year,
                is_archived=False,
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    "يوجد اشتراك نقل مسجل لهذا الطالب في العام الدراسي المحدد."
                )
        return attrs


class LibraryBookSerializer(SchoolServiceSerializer):
    total_copies = serializers.IntegerField(min_value=1)

    class Meta(SchoolServiceSerializer.Meta):
        model = LibraryBook
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "available_copies",
        )

    def create(self, validated_data):
        validated_data["available_copies"] = validated_data.get("total_copies", 1)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        old_total = instance.total_copies
        outstanding = old_total - instance.available_copies
        new_total = validated_data.get("total_copies", old_total)
        if new_total < outstanding:
            raise serializers.ValidationError({
                "total_copies": "لا يمكن خفض عدد النسخ عن عدد النسخ المعارة حالياً."
            })
        # LibraryBook.save recalculates available copies under a row lock.
        validated_data.pop("available_copies", None)
        return super().update(instance, validated_data)


class BookLoanSerializer(SchoolServiceSerializer):
    due_date = serializers.DateField(required=False)
    is_overdue = serializers.SerializerMethodField()
    overdue_days = serializers.SerializerMethodField()

    class Meta(SchoolServiceSerializer.Meta):
        model = BookLoan
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "status", "return_date", "fine_amount", "fine_invoice",
            "renewal_count", "is_overdue", "overdue_days",
        )

    def get_overdue_days(self, obj):
        if obj.status not in {
            BookLoan.Status.BORROWED,
            BookLoan.Status.OVERDUE,
        }:
            return 0
        return max(0, (timezone.localdate() - obj.due_date).days)

    def get_is_overdue(self, obj):
        return self.get_overdue_days(obj) > 0

    def validate(self, attrs):
        attrs = super().validate(attrs)
        student = attrs.get("student", getattr(self.instance, "student", None))
        teacher = attrs.get("teacher", getattr(self.instance, "teacher", None))
        if bool(student) == bool(teacher):
            raise serializers.ValidationError(
                "يجب تحديد مستعير واحد فقط: طالب أو معلم."
            )
        borrow_date = attrs.get(
            "borrow_date", getattr(self.instance, "borrow_date", None)
        )
        if self.instance is None and borrow_date is None:
            borrow_date = timezone.localdate()
        due_date = attrs.get("due_date", getattr(self.instance, "due_date", None))
        if self.instance is None and due_date is None and borrow_date:
            school = self.context.get("school")
            policy = SchoolSettings.objects.filter(school=school).only(
                "library_default_loan_days"
            ).first()
            loan_days = policy.library_default_loan_days if policy else 14
            due_date = borrow_date + timedelta(days=loan_days)
            attrs["due_date"] = due_date
        if borrow_date and due_date and due_date < borrow_date:
            raise serializers.ValidationError({
                "due_date": "يجب أن يكون موعد الإرجاع في تاريخ الاستعارة أو بعده."
            })
        return attrs


class BusFinancialSettlementSerializer(SchoolServiceSerializer):
    advances_withdrawn = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00")
    )

    class Meta(SchoolServiceSerializer.Meta):
        model = BusFinancialSettlement
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "student_count", "rate_applied", "gross_due", "net_payable",
            "status", "approved_by", "payment_voucher",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        route = attrs.get("bus_route", getattr(self.instance, "bus_route", None))
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        month = attrs.get("month", getattr(self.instance, "month", None))
        fiscal_year = attrs.get("year", getattr(self.instance, "year", None))
        if month is not None and not 1 <= month <= 12:
            raise serializers.ValidationError({"month": "يجب أن يكون الشهر بين 1 و12."})
        if route and year and month and fiscal_year:
            exists = BusFinancialSettlement.objects.filter(
                school=self.context["school"],
                bus_route=route,
                academic_year=year,
                year=fiscal_year,
                month=month,
                is_archived=False,
            )
            if self.instance:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise serializers.ValidationError(
                    "توجد تسوية مالية لهذا الخط والسنة والشهر بالفعل."
                )
        return attrs


class StudentBookDistributionSerializer(SchoolServiceSerializer):
    quantity = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0.01")
    )
    fee_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.00")
    )

    class Meta(SchoolServiceSerializer.Meta):
        model = StudentBookDistribution
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "delivery_status", "delivered_at", "delivered_by", "returned_at",
            "returned_by", "invoice",
        )


class BookRequisitionItemSerializer(serializers.ModelSerializer):
    quantity_requested = serializers.IntegerField(min_value=1)

    class Meta:
        model = BookRequisitionItem
        fields = (
            "id", "book_title", "quantity_requested", "quantity_approved",
            "quantity_dispatched", "notes",
        )
        read_only_fields = ("id", "quantity_approved", "quantity_dispatched")


class BookRequisitionOrderSerializer(SchoolServiceSerializer):
    items = BookRequisitionItemSerializer(many=True, required=False)

    class Meta(SchoolServiceSerializer.Meta):
        model = BookRequisitionOrder
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "order_number", "requested_by", "status", "approved_by",
            "approved_at", "fulfilled_by", "fulfilled_at",
        )

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items", [])
        order = BookRequisitionOrder.objects.create(**validated_data)
        for item in items:
            BookRequisitionItem.objects.create(
                school=order.school, requisition=order, **item
            )
        return order

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["items"] = BookRequisitionItemSerializer(
            instance.items.all(), many=True
        ).data
        return data

