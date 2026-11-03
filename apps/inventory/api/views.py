"""Tenant-isolated procurement and inventory API views."""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum, F, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import require_school_role_or_permission, resolve_active_school
from apps.accounting.models import Account
from apps.inventory.api.serializers import (
    InventoryItemSerializer,
    PurchaseOrderCreateSerializer,
    PurchaseOrderSerializer,
    PurchaseReceiptInputSerializer,
    StockMovementCreateSerializer,
    StockMovementSerializer,
    SupplierSerializer,
    VendorInvoiceSerializer,
    VendorPaymentInputSerializer,
    WarehouseSerializer,
    WarehouseStockSerializer,
)
from apps.inventory.models import (
    InventoryItem,
    PurchaseOrder,
    StockMovement,
    Supplier,
    VendorInvoice,
    Warehouse,
    WarehouseStock,
    WarehouseTransfer,
)
from apps.inventory.services import (
    approve_purchase_order,
    approve_vendor_invoice,
    cancel_purchase_order,
    pay_vendor_invoice,
    post_warehouse_transfer,
    receive_purchase_order,
    record_stock_movement,
    reverse_stock_movement,
    reverse_warehouse_transfer,
)


def _school(request):
    school = resolve_active_school(request)
    if school is None:
        raise PermissionDenied("لم يتم تحديد مدرسة نشطة أو عضوية سارية.")
    return school


def _authorize(request, permission: str):
    require_school_role_or_permission(request, _school(request), set(), permission)


def _django_validation(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages) from exc


class SchoolListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    model = None
    serializer_class = None
    app_label = "inventory"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        action = "view" if request.method == "GET" else "add"
        _authorize(request, f"{self.app_label}.{action}_{self.model._meta.model_name}")

    def get_queryset(self):
        return self.model.objects.filter(
            school=_school(self.request), is_archived=False,
        ).order_by("-created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_create(self, serializer):
        serializer.save(school=_school(self.request))


class SchoolDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    model = None
    serializer_class = None
    app_label = "inventory"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        action = {
            "GET": "view", "PUT": "change", "PATCH": "change", "DELETE": "delete",
        }.get(request.method, "view")
        _authorize(request, f"{self.app_label}.{action}_{self.model._meta.model_name}")

    def get_queryset(self):
        return self.model.objects.filter(
            school=_school(self.request), is_archived=False,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_destroy(self, instance):
        instance.archive(actor=self.request.user, reason="أرشفة عبر واجهة API")


class SupplierListCreateAPIView(SchoolListCreateAPIView):
    model = Supplier
    serializer_class = SupplierSerializer


class SupplierDetailAPIView(SchoolDetailAPIView):
    model = Supplier
    serializer_class = SupplierSerializer


class WarehouseListCreateAPIView(SchoolListCreateAPIView):
    model = Warehouse
    serializer_class = WarehouseSerializer


class WarehouseDetailAPIView(SchoolDetailAPIView):
    model = Warehouse
    serializer_class = WarehouseSerializer


class ItemListCreateAPIView(SchoolListCreateAPIView):
    model = InventoryItem
    serializer_class = InventoryItemSerializer


class ItemDetailAPIView(SchoolDetailAPIView):
    model = InventoryItem
    serializer_class = InventoryItemSerializer


class StockMovementListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StockMovementSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(
            request,
            "inventory.view_stockmovement" if request.method == "GET"
            else "inventory.add_stockmovement",
        )

    def get_queryset(self):
        return StockMovement.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("item", "warehouse", "created_by").order_by("-date", "-created_at")

    def get_serializer_class(self):
        return StockMovementCreateSerializer if self.request.method == "POST" else StockMovementSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        movement, created = _django_validation(
            record_stock_movement,
            school=_school(request),
            item=data["item"],
            warehouse=data.get("warehouse"),
            movement_type=data["movement_type"],
            quantity=data["quantity"],
            unit_cost=data["unit_cost"],
            idempotency_key=data["idempotency_key"],
            notes=data["notes"],
            date_value=data.get("date"),
            reference=data.get("reference", ""),
            recipient_name=data.get("recipient_name", ""),
            created_by=request.user,
        )
        result = StockMovementSerializer(movement, context={"school": _school(request)})
        return Response(result.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class StockMovementReverseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "inventory.reverse_stockmovement")
        movement = get_object_or_404(
            StockMovement, pk=pk, school=_school(request), is_archived=False,
        )
        key = request.data.get("idempotency_key", "")
        reason = request.data.get("reason", "")
        reversed_movement = _django_validation(
            reverse_stock_movement,
            movement=movement,
            idempotency_key=key,
            reason=reason,
            reversed_by=request.user,
        )
        return Response(StockMovementSerializer(reversed_movement).data, status=status.HTTP_201_CREATED)


class WarehouseStockListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WarehouseStockSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(request, "inventory.view_warehousestock")

    def get_queryset(self):
        queryset = WarehouseStock.objects.filter(
            school=_school(self.request), is_archived=False,
            quantity__gt=0,
        ).select_related("item", "warehouse").order_by("warehouse__name", "item__name")
        warehouse_id = self.request.query_params.get("warehouse")
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(item__name__icontains=search) | Q(item__code__icontains=search))
        return queryset


class PurchaseOrderListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseOrderSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(
            request,
            "inventory.view_purchaseorder" if request.method == "GET"
            else "inventory.add_purchaseorder",
        )

    def get_queryset(self):
        return PurchaseOrder.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("supplier", "warehouse", "approved_by").prefetch_related("items").order_by("-order_date", "-created_at")

    def get_serializer_class(self):
        return PurchaseOrderCreateSerializer if self.request.method == "POST" else PurchaseOrderSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_create(self, serializer):
        serializer.save(school=_school(self.request))


class PurchaseOrderDetailAPIView(SchoolDetailAPIView):
    model = PurchaseOrder
    serializer_class = PurchaseOrderSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("supplier", "warehouse").prefetch_related("items")


class PurchaseOrderApproveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "inventory.approve_purchaseorder")
        order = get_object_or_404(PurchaseOrder, pk=pk, school=_school(request), is_archived=False)
        order = _django_validation(approve_purchase_order, purchase_order=order, approved_by=request.user)
        return Response(PurchaseOrderSerializer(order, context={"school": _school(request)}).data)


class PurchaseOrderReceiveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "inventory.receive_purchaseorder")
        order = get_object_or_404(PurchaseOrder, pk=pk, school=_school(request), is_archived=False)
        serializer = PurchaseReceiptInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        receipt, created = _django_validation(
            receive_purchase_order,
            purchase_order=order,
            received_items=serializer.validated_data["received_items"],
            idempotency_key=serializer.validated_data["idempotency_key"],
            received_by=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )
        return Response(
            {
                "id": str(receipt.pk),
                "receipt_number": receipt.receipt_number,
                "purchase_order": str(order.pk),
                "created": created,
                "status": PurchaseOrder.objects.get(pk=order.pk).status,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PurchaseOrderCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "inventory.cancel_purchaseorder")
        order = get_object_or_404(PurchaseOrder, pk=pk, school=_school(request), is_archived=False)
        order = _django_validation(cancel_purchase_order, purchase_order=order, cancelled_by=request.user)
        return Response({"id": str(order.pk), "status": order.status})


class VendorInvoiceListCreateAPIView(SchoolListCreateAPIView):
    model = VendorInvoice
    serializer_class = VendorInvoiceSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("supplier", "purchase_order", "journal_entry")


class VendorInvoiceDetailAPIView(SchoolDetailAPIView):
    model = VendorInvoice
    serializer_class = VendorInvoiceSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("supplier", "purchase_order", "journal_entry")


class VendorInvoiceApproveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "inventory.approve_vendorinvoice")
        invoice = get_object_or_404(VendorInvoice, pk=pk, school=_school(request), is_archived=False)
        invoice, entry = _django_validation(approve_vendor_invoice, invoice=invoice, approved_by=request.user)
        return Response({
            "id": str(invoice.pk), "status": invoice.status,
            "journal_entry": entry.entry_number,
            "approved_at": invoice.approved_at,
        })


class VendorInvoicePayAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _authorize(request, "inventory.pay_vendorinvoice")
        invoice = get_object_or_404(VendorInvoice, pk=pk, school=_school(request), is_archived=False)
        serializer = VendorPaymentInputSerializer(data=request.data, context={"school": _school(request)})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        entry, voucher = _django_validation(
            pay_vendor_invoice,
            invoice=invoice,
            payment_account=data["payment_account"],
            amount=data["amount"],
            idempotency_key=data["idempotency_key"],
            reference_number=data.get("reference_number", ""),
            payment_method=data["payment_method"],
            user=request.user,
        )
        invoice.refresh_from_db()
        return Response({
            "invoice_id": str(invoice.pk),
            "paid_amount": invoice.paid_amount,
            "remaining_amount": invoice.remaining_amount,
            "status": invoice.status,
            "voucher_number": voucher.voucher_number,
            "journal_entry": entry.entry_number,
        })


class WarehouseTransferListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _authorize(
            request,
            "inventory.view_warehousetransfer" if request.method == "GET"
            else "inventory.add_warehousetransfer",
        )

    def get_queryset(self):
        return WarehouseTransfer.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("item", "source_warehouse", "destination_warehouse").order_by("-transfer_date", "-created_at")

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        data = page if page is not None else queryset
        rows = [{
            "id": str(row.pk), "transfer_number": row.transfer_number,
            "item": str(row.item_id), "item_name": row.item.name,
            "source_warehouse": str(row.source_warehouse_id),
            "source_warehouse_name": row.source_warehouse.name,
            "destination_warehouse": str(row.destination_warehouse_id),
            "destination_warehouse_name": row.destination_warehouse.name,
            "quantity": row.quantity, "unit_cost": row.unit_cost,
            "status": row.status, "transfer_date": row.transfer_date,
            "idempotency_key": row.idempotency_key, "notes": row.notes,
        } for row in data]
        return self.get_paginated_response(rows) if page is not None else Response(rows)

    def post(self, request, *args, **kwargs):
        from rest_framework import serializers
        from apps.inventory.api.serializers import WarehouseTransferCreateSerializer

        serializer = WarehouseTransferCreateSerializer(data=request.data, context={"school": _school(request)})
        serializer.is_valid(raise_exception=True)
        transfer = serializer.save(school=_school(request))
        return Response({"id": str(transfer.pk), "status": transfer.status}, status=status.HTTP_201_CREATED)


class WarehouseTransferWorkflowAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, action):
        transfer = get_object_or_404(
            WarehouseTransfer, pk=pk, school=_school(request), is_archived=False,
        )
        if action == "post":
            _authorize(request, "inventory.post_warehousetransfer")
            transfer = _django_validation(post_warehouse_transfer, transfer=transfer, posted_by=request.user)
        elif action == "reverse":
            _authorize(request, "inventory.reverse_warehousetransfer")
            transfer = _django_validation(
                reverse_warehouse_transfer,
                transfer=transfer,
                reason=request.data.get("reason", ""),
                reversed_by=request.user,
            )
        else:
            return Response({"detail": "Unknown action."}, status=status.HTTP_404_NOT_FOUND)
        transfer.refresh_from_db()
        return Response({"id": str(transfer.pk), "status": transfer.status})
