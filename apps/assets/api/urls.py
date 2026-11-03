from django.urls import path

from apps.assets.api.views import (
    AssetCategoryDetailAPIView,
    AssetCategoryListCreateAPIView,
    AssetDepreciationListAPIView,
    AssetDisposalListAPIView,
    AssetMovementListAPIView,
    DisposeAssetAPIView,
    FixedAssetListAPIView,
    GenerateAssetDepreciationAPIView,
    MoveAssetAPIView,
    RegisterAssetFromInvoiceAPIView,
)

urlpatterns = [
    path("categories/", AssetCategoryListCreateAPIView.as_view(), name="asset-category-list-create"),
    path("categories/<uuid:pk>/", AssetCategoryDetailAPIView.as_view(), name="asset-category-detail"),
    path("", FixedAssetListAPIView.as_view(), name="asset-list"),
    path("register-from-invoice/", RegisterAssetFromInvoiceAPIView.as_view(), name="asset-register-from-invoice"),
    path("depreciation/", AssetDepreciationListAPIView.as_view(), name="asset-depreciation-list"),
    path("depreciation/generate/", GenerateAssetDepreciationAPIView.as_view(), name="asset-depreciation-generate"),
    path("movements/", AssetMovementListAPIView.as_view(), name="asset-movement-list"),
    path("<uuid:pk>/move/", MoveAssetAPIView.as_view(), name="asset-move"),
    path("disposals/", AssetDisposalListAPIView.as_view(), name="asset-disposal-list"),
    path("<uuid:pk>/dispose/", DisposeAssetAPIView.as_view(), name="asset-dispose"),
]
