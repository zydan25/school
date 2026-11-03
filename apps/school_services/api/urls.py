"""Versioned API routes for optional school services."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BookLoanViewSet,
    BookRequisitionOrderViewSet,
    BusFinancialSettlementViewSet,
    BusRouteViewSet,
    BusSubscriptionChargeViewSet,
    LibraryBookViewSet,
    LibraryPolicyView,
    SchoolServiceFeaturesView,
    StudentBookDistributionViewSet,
    StudentBusSubscriptionViewSet,
)

app_name = "school_services_api"

router = DefaultRouter()
router.register("bus-routes", BusRouteViewSet, basename="school-bus-route")
router.register("bus-subscriptions", StudentBusSubscriptionViewSet, basename="school-bus-subscription")
router.register("bus-charges", BusSubscriptionChargeViewSet, basename="school-bus-charge")
router.register("library/books", LibraryBookViewSet, basename="school-library-book")
router.register("library/loans", BookLoanViewSet, basename="school-library-loan")
router.register("bus-settlements", BusFinancialSettlementViewSet, basename="school-bus-settlement")
router.register("book-distributions", StudentBookDistributionViewSet, basename="school-book-distribution")
router.register("book-requisitions", BookRequisitionOrderViewSet, basename="school-book-requisition")

urlpatterns = [
    path("features/", SchoolServiceFeaturesView.as_view(), name="school-service-features"),
    path("library/policy/", LibraryPolicyView.as_view(), name="school-library-policy"),
    *router.urls,
]
