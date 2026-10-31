"""Serializers for the school support-services API."""
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import SchoolMembership
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


class BusRouteSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = BusRoute
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields


class StudentBusSubscriptionSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = StudentBusSubscription
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields


class LibraryBookSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = LibraryBook
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "available_copies",
        )


class BookLoanSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = BookLoan
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "status", "return_date",
        )


class BusFinancialSettlementSerializer(SchoolServiceSerializer):
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
    class Meta(SchoolServiceSerializer.Meta):
        model = StudentBookDistribution
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields + (
            "delivery_status", "delivered_at", "delivered_by", "returned_at",
            "returned_by", "invoice",
        )


class BookRequisitionItemSerializer(serializers.ModelSerializer):
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


class StudentHealthProfileSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = StudentHealthProfile
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields


class ClinicVisitSerializer(SchoolServiceSerializer):
    class Meta(SchoolServiceSerializer.Meta):
        model = ClinicVisit
        fields = "__all__"
        read_only_fields = SchoolServiceSerializer.Meta.read_only_fields
