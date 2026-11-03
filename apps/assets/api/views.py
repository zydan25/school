"""School-scoped fixed asset API views."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import require_school_role_or_permission, resolve_active_school
from apps.assets.api.serializers import (
    AssetCategorySerializer,
    AssetDepreciationSerializer,
    AssetDisposalSerializer,
    AssetMovementSerializer,
    DisposeAssetSerializer,
    FixedAssetSerializer,
    GenerateAssetDepreciationSerializer,
    MoveAssetSerializer,
    RegisterAssetFromInvoiceSerializer,
)
from apps.assets.models import (
    AssetCategory,
    AssetDepreciationEntry,
    AssetDisposal,
    AssetMovement,
    FixedAsset,
)
from apps.assets.services import (
    dispose_asset,
    generate_asset_depreciation,
    move_asset,
    register_asset_from_vendor_invoice,
)


def _school(request):
    school = resolve_active_school(request)
    if school is None:
        raise PermissionDenied("لم يتم تحديد مدرسة نشطة أو عضوية سارية.")
    return school


def _authorize(request, permission):
    require_school_role_or_permission(request, _school(request), set(), permission)


def _django_validation(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages) from exc


class AssetCategoryListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssetCategorySerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(request, "assets.view_assetcategory" if request.method == "GET" else "assets.add_assetcategory")

    def get_queryset(self):
        return AssetCategory.objects.filter(school=_school(self.request), is_archived=False).order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_create(self, serializer):
        try:
            serializer.save(school=_school(self.request))
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc


class AssetCategoryDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssetCategorySerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        action = {"GET": "view", "PUT": "change", "PATCH": "change", "DELETE": "delete"}.get(request.method, "view")
        _authorize(request, f"assets.{action}_assetcategory")

    def get_queryset(self):
        return AssetCategory.objects.filter(school=_school(self.request), is_archived=False)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_update(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

    def perform_destroy(self, instance):
        if instance.assets.filter(is_archived=False).exists():
            raise ValidationError("لا يمكن أرشفة تصنيف مستخدم في أصول قائمة.")
        try:
            instance.archive(actor=self.request.user, reason="أرشفة عبر API")
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc


class FixedAssetListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FixedAssetSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(request, "assets.view_fixedasset")

    def get_queryset(self):
        queryset = FixedAsset.objects.filter(school=_school(self.request), is_archived=False).select_related(
            "category", "custodian__user", "source_vendor_invoice", "acquisition_journal_entry",
        ).order_by("code")
        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context


class RegisterAssetFromInvoiceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _authorize(request, "assets.add_fixedasset")
        serializer = RegisterAssetFromInvoiceSerializer(data=request.data, context={"school": _school(request)})
        serializer.is_valid(raise_exception=True)
        asset = _django_validation(
            register_asset_from_vendor_invoice,
            **serializer.validated_data,
            registered_by=request.user,
        )
        return Response(FixedAssetSerializer(asset, context={"school": _school(request)}).data, status=status.HTTP_201_CREATED)


class AssetDepreciationListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssetDepreciationSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(request, "assets.view_assetdepreciationentry")

    def get_queryset(self):
        queryset = AssetDepreciationEntry.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("asset", "fiscal_year", "journal_entry", "posted_by").order_by("-date")
        asset = self.request.query_params.get("asset")
        if asset:
            queryset = queryset.filter(asset_id=asset)
        year = self.request.query_params.get("fiscal_year")
        if year:
            queryset = queryset.filter(fiscal_year_id=year)
        return queryset


class GenerateAssetDepreciationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _authorize(request, "assets.post_assetdepreciationentry")
        serializer = GenerateAssetDepreciationSerializer(data=request.data, context={"school": _school(request)})
        serializer.is_valid(raise_exception=True)
        result = _django_validation(
            generate_asset_depreciation,
            asset=serializer.validated_data["asset"],
            fiscal_year=serializer.validated_data["fiscal_year"],
            posted_by=request.user,
            post=serializer.validated_data["post"],
        )
        return Response(AssetDepreciationSerializer(result).data, status=status.HTTP_201_CREATED if not result.pk else status.HTTP_200_OK)


class AssetMovementListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssetMovementSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(request, "assets.view_assetmovement")

    def get_queryset(self):
        return AssetMovement.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("asset", "from_branch", "to_branch", "from_custodian", "to_custodian").order_by("-movement_date")


class MoveAssetAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "assets.move_assetmovement")
        asset = get_object_or_404(FixedAsset, pk=pk, school=_school(request), is_archived=False)
        serializer = MoveAssetSerializer(data=request.data, context={"school": _school(request)})
        serializer.is_valid(raise_exception=True)
        movement = _django_validation(
            move_asset, asset=asset, recorded_by=request.user, **serializer.validated_data,
        )
        return Response(AssetMovementSerializer(movement).data, status=status.HTTP_201_CREATED)


class AssetDisposalListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssetDisposalSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(request, "assets.view_assetdisposal")

    def get_queryset(self):
        return AssetDisposal.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("asset", "payment_account", "journal_entry", "disposed_by").order_by("-disposal_date")


class DisposeAssetAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "assets.dispose_assetdisposal")
        asset = get_object_or_404(FixedAsset, pk=pk, school=_school(request), is_archived=False)
        serializer = DisposeAssetSerializer(data=request.data, context={"school": _school(request)})
        serializer.is_valid(raise_exception=True)
        disposal = _django_validation(
            dispose_asset, asset=asset, disposed_by=request.user, **serializer.validated_data,
        )
        return Response(AssetDisposalSerializer(disposal).data, status=status.HTTP_201_CREATED)
