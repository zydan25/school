"""Versioned API routes for school support services."""
from rest_framework.routers import DefaultRouter

from .views import (
    BookLoanViewSet,
    BookRequisitionOrderViewSet,
    BusFinancialSettlementViewSet,
    BusRouteViewSet,
    ClinicVisitViewSet,
    LibraryBookViewSet,
    StudentBookDistributionViewSet,
    StudentBusSubscriptionViewSet,
    StudentHealthProfileViewSet,
)

app_name = "school_services_api"

router = DefaultRouter()
router.register("bus-routes", BusRouteViewSet, basename="school-bus-route")
router.register("bus-subscriptions", StudentBusSubscriptionViewSet, basename="school-bus-subscription")
router.register("library/books", LibraryBookViewSet, basename="school-library-book")
router.register("library/loans", BookLoanViewSet, basename="school-library-loan")
router.register("bus-settlements", BusFinancialSettlementViewSet, basename="school-bus-settlement")
router.register("book-distributions", StudentBookDistributionViewSet, basename="school-book-distribution")
router.register("book-requisitions", BookRequisitionOrderViewSet, basename="school-book-requisition")
router.register("clinic/health-profiles", StudentHealthProfileViewSet, basename="school-health-profile")
router.register("clinic/visits", ClinicVisitViewSet, basename="school-clinic-visit")

urlpatterns = router.urls
