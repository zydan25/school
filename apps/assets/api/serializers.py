"""School-scoped fixed-asset serializers."""
from decimal import Decimal

from rest_framework import serializers

from apps.accounting.models import Account, FiscalYear, JournalEntry
from apps.assets.models import (
    AssetCategory,
    AssetDepreciationEntry,
    AssetDisposal,
    AssetMovement,
    FixedAsset,
)
from apps.inventory.models import VendorInvoice
from apps.staff.models import Teacher
from apps.tenants.models import Branch


class AssetCategorySerializer(serializers.ModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none(), required=False, allow_null=True)

    class Meta:
        model = AssetCategory
        fields = [
            "id", "branch", "code", "name", "annual_depreciation_rate",
            "useful_life_years", "asset_account", "depreciation_expense_account",
            "accumulated_depreciation_account", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["branch"].queryset = Branch.objects.filter(
            school=school, is_archived=False,
        ) if school else Branch.objects.none()
        for field in ("asset_account", "depreciation_expense_account", "accumulated_depreciation_account"):
            self.fields[field].queryset = Account.objects.filter(
                school=school, is_archived=False, is_leaf=True,
            ) if school else Account.objects.none()

    def validate(self, attrs):
        rate = attrs.get("annual_depreciation_rate", getattr(self.instance, "annual_depreciation_rate", Decimal("10")))
        life = attrs.get("useful_life_years", getattr(self.instance, "useful_life_years", 5))
        if rate < 0 or rate > 100:
            raise serializers.ValidationError({"annual_depreciation_rate": "النسبة يجب أن تكون بين صفر و100."})
        if life <= 0:
            raise serializers.ValidationError({"useful_life_years": "العمر الإنتاجي يجب أن يكون أكبر من صفر."})
        school = self.context["school"]
        for field in ("asset_account", "depreciation_expense_account", "accumulated_depreciation_account"):
            account = attrs.get(field, getattr(self.instance, field, None))
            if account and account.school_id != school.pk:
                raise serializers.ValidationError({field: "الحساب لا يتبع المدرسة الحالية."})
        return attrs


class FixedAssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    custodian_name = serializers.SerializerMethodField()
    current_book_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = FixedAsset
        fields = [
            "id", "branch", "category", "category_name", "code", "name",
            "purchase_date", "purchase_cost", "salvage_value",
            "accumulated_depreciation", "current_book_value", "location_room",
            "custodian", "custodian_name", "status", "source_vendor_invoice",
            "acquisition_journal_entry", "disposal_journal_entry", "disposed_at",
            "created_at",
        ]
        read_only_fields = [
            "id", "purchase_cost", "accumulated_depreciation", "current_book_value",
            "status", "source_vendor_invoice", "acquisition_journal_entry",
            "disposal_journal_entry", "disposed_at", "created_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["category"].queryset = AssetCategory.objects.filter(
            school=school, is_archived=False,
        ) if school else AssetCategory.objects.none()
        self.fields["custodian"].queryset = Teacher.objects.filter(
            school=school, is_archived=False,
        ) if school else Teacher.objects.none()
        self.fields["branch"].queryset = Branch.objects.filter(
            school=school, is_archived=False,
        ) if school else Branch.objects.none()

    def get_custodian_name(self, obj):
        return obj.custodian.user.get_full_name() if obj.custodian_id else ""

    def validate(self, attrs):
        school = self.context["school"]
        for field in ("category", "custodian", "branch"):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value and value.school_id != school.pk:
                raise serializers.ValidationError({field: "القيمة المحددة لا تتبع المدرسة الحالية."})
        return attrs


class AssetDepreciationSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.code", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    fiscal_year_name = serializers.CharField(source="fiscal_year.name", read_only=True)
    journal_entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True, allow_null=True)

    class Meta:
        model = AssetDepreciationEntry
        fields = [
            "id", "asset", "asset_code", "asset_name", "fiscal_year",
            "fiscal_year_name", "depreciation_amount", "date", "journal_entry",
            "journal_entry_number", "posted_at", "posted_by", "created_at",
        ]
        read_only_fields = fields


class AssetMovementSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.code", read_only=True)

    class Meta:
        model = AssetMovement
        fields = [
            "id", "asset", "asset_code", "movement_type", "from_branch",
            "to_branch", "from_location", "to_location", "from_custodian",
            "to_custodian", "movement_date", "idempotency_key", "reason",
            "recorded_by", "created_at",
        ]
        read_only_fields = fields


class AssetDisposalSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.code", read_only=True)
    journal_entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True, allow_null=True)

    class Meta:
        model = AssetDisposal
        fields = [
            "id", "asset", "asset_code", "disposal_date", "proceeds",
            "payment_account", "journal_entry", "journal_entry_number",
            "idempotency_key", "reason", "disposed_by", "created_at",
        ]
        read_only_fields = fields


class RegisterAssetFromInvoiceSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=VendorInvoice.objects.none())
    category = serializers.PrimaryKeyRelatedField(queryset=AssetCategory.objects.none())
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    purchase_date = serializers.DateField()
    purchase_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False)
    salvage_value = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    location_room = serializers.CharField(max_length=150, required=False, allow_blank=True)
    custodian = serializers.PrimaryKeyRelatedField(queryset=Teacher.objects.none(), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["invoice"].queryset = VendorInvoice.objects.filter(
            school=school, is_archived=False,
        ) if school else VendorInvoice.objects.none()
        self.fields["category"].queryset = AssetCategory.objects.filter(
            school=school, is_archived=False,
        ) if school else AssetCategory.objects.none()
        self.fields["custodian"].queryset = Teacher.objects.filter(
            school=school, is_archived=False,
        ) if school else Teacher.objects.none()


class GenerateAssetDepreciationSerializer(serializers.Serializer):
    asset = serializers.PrimaryKeyRelatedField(queryset=FixedAsset.objects.none())
    fiscal_year = serializers.PrimaryKeyRelatedField(queryset=FiscalYear.objects.none())
    post = serializers.BooleanField(default=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["asset"].queryset = FixedAsset.objects.filter(
            school=school, is_archived=False,
        ) if school else FixedAsset.objects.none()
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(
            school=school, is_archived=False,
        ) if school else FiscalYear.objects.none()


class MoveAssetSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(min_length=8, max_length=100)
    reason = serializers.CharField(max_length=500)
    movement_date = serializers.DateField(required=False)
    to_branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none(), required=False, allow_null=True)
    to_location = serializers.CharField(max_length=150, required=False, allow_blank=True)
    to_custodian = serializers.PrimaryKeyRelatedField(queryset=Teacher.objects.none(), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["to_branch"].queryset = Branch.objects.filter(
            school=school, is_archived=False,
        ) if school else Branch.objects.none()
        self.fields["to_custodian"].queryset = Teacher.objects.filter(
            school=school, is_archived=False,
        ) if school else Teacher.objects.none()


class DisposeAssetSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(min_length=8, max_length=100)
    reason = serializers.CharField(max_length=500)
    disposal_date = serializers.DateField(required=False)
    proceeds = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    payment_account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none(), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["payment_account"].queryset = Account.objects.filter(
            school=school, is_archived=False, is_leaf=True,
            account_type=Account.AccountType.ASSET,
        ) if school else Account.objects.none()

    def validate(self, attrs):
        if attrs.get("proceeds", Decimal("0")) > 0 and not attrs.get("payment_account"):
            raise serializers.ValidationError({"payment_account": "حساب تحصيل المتحصل مطلوب عند وجود قيمة بيع."})
        return attrs
