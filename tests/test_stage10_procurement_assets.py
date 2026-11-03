from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounting.models import Account, FiscalPeriod, FiscalYear
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.assets.models import AssetCategory, AssetDepreciationEntry, FixedAsset
from apps.assets.services import (
    dispose_asset,
    generate_asset_depreciation,
    move_asset,
    register_asset_from_vendor_invoice,
)
from apps.inventory.models import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
    VendorInvoice,
    VendorInvoicePayment,
    Warehouse,
    WarehouseStock,
)
from apps.inventory.services import (
    approve_purchase_order,
    approve_vendor_invoice,
    pay_vendor_invoice,
    receive_purchase_order,
    record_stock_movement,
    reverse_stock_movement,
)
from apps.accounts.models import User
from apps.tenants.models import Branch, School
from apps.tenants.services import provision_school


class Stage10ProcurementAssetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+967770001010",
            password="StrongPassword123!",
            first_name="اختبار",
            last_name="المرحلة العاشرة",
        )
        self.school = School.objects.create(
            owner=self.owner,
            name="مدرسة اختبارات المرحلة العاشرة",
            code="STAGE10",
            status=School.Status.ACTIVE,
        )
        provision_school(self.school)
        seed_default_chart_of_accounts(self.school)
        self.year = FiscalYear.objects.create(
            school=self.school,
            name="السنة المالية 2026 للاختبار",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.period = FiscalPeriod.objects.create(
            school=self.school,
            fiscal_year=self.year,
            period_number=1,
            name="الفترة السنوية للاختبار",
            start_date=self.year.start_date,
            end_date=self.year.end_date,
        )
        self.supplier = Supplier.objects.create(
            school=self.school,
            code="SUP-10",
            name="مورد تجريبي",
            phone="770000010",
        )
        self.warehouse = Warehouse.objects.create(
            school=self.school,
            code="WH-10",
            name="المستودع الرئيسي",
        )
        self.item = InventoryItem.objects.create(
            school=self.school,
            code="ITEM-10",
            name="ورق طباعة A4",
            warehouse=self.warehouse,
            unit=InventoryItem.Unit.BOX,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("10.00"),
            reorder_level=Decimal("2.00"),
        )

    def test_stock_ledger_is_idempotent_and_cannot_be_edited_or_deleted(self):
        receipt, created = record_stock_movement(
            school=self.school,
            item=self.item,
            warehouse=self.warehouse,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("100.00"),
            unit_cost=Decimal("12.00"),
            idempotency_key="stage10-stock-001",
            notes="رصيد توريد افتتاحي تجريبي",
            created_by=self.owner,
        )
        self.assertTrue(created)
        replay, created_again = record_stock_movement(
            school=self.school,
            item=self.item,
            warehouse=self.warehouse,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("100.00"),
            unit_cost=Decimal("12.00"),
            idempotency_key="stage10-stock-001",
            notes="إعادة طلب الشبكة",
            created_by=self.owner,
        )
        self.assertFalse(created_again)
        self.assertEqual(replay.pk, receipt.pk)

        issue, _ = record_stock_movement(
            school=self.school,
            item=self.item,
            warehouse=self.warehouse,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity=Decimal("25.00"),
            unit_cost=Decimal("12.00"),
            idempotency_key="stage10-stock-002",
            notes="صرف إلى قسم الحاسب",
            recipient_name="قسم الحاسب",
            created_by=self.owner,
        )
        balance = WarehouseStock.objects.get(
            school=self.school, item=self.item, warehouse=self.warehouse,
        )
        self.assertEqual(balance.quantity, Decimal("75.00"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("75.00"))

        reversed_issue = reverse_stock_movement(
            movement=issue,
            idempotency_key="stage10-stock-reverse-002",
            reason="إلغاء سند الصرف التجريبي",
            reversed_by=self.owner,
        )
        self.assertEqual(reversed_issue.reversal_of_id, issue.pk)
        balance.refresh_from_db()
        self.assertEqual(balance.quantity, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            StockMovement.objects.filter(pk=receipt.pk).update(quantity=Decimal("1"))
        with self.assertRaises(ValidationError):
            receipt.delete()

    def test_stock_issue_cannot_make_balance_negative(self):
        with self.assertRaises(ValidationError):
            record_stock_movement(
                school=self.school,
                item=self.item,
                warehouse=self.warehouse,
                movement_type=StockMovement.MovementType.ISSUE,
                quantity=Decimal("1.00"),
                unit_cost=Decimal("0.00"),
                idempotency_key="stage10-stock-low",
                notes="محاولة صرف دون رصيد",
                created_by=self.owner,
            )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("0.00"))

    def test_purchase_order_partial_receipts_are_atomic_and_idempotent(self):
        order = PurchaseOrder.objects.create(
            school=self.school,
            order_number="PO-ST10-001",
            supplier=self.supplier,
            warehouse=self.warehouse,
            order_date=timezone.localdate(),
        )
        line = PurchaseOrderItem.objects.create(
            school=self.school,
            purchase_order=order,
            item=self.item,
            quantity=Decimal("10.00"),
            unit_price=Decimal("15.00"),
            total_price=Decimal("150.00"),
        )
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("150.00"))
        order = approve_purchase_order(purchase_order=order, approved_by=self.owner)
        self.assertEqual(order.status, PurchaseOrder.Status.APPROVED)

        receipt, created = receive_purchase_order(
            purchase_order=order,
            received_items=[{"purchase_order_item_id": str(line.pk), "quantity": "4.00"}],
            idempotency_key="stage10-grn-001",
            received_by=self.owner,
            notes="استلام الدفعة الأولى",
        )
        self.assertTrue(created)
        replay, created_again = receive_purchase_order(
            purchase_order=order,
            received_items=[{"purchase_order_item_id": str(line.pk), "quantity": "4.00"}],
            idempotency_key="stage10-grn-001",
            received_by=self.owner,
            notes="إعادة إرسال نفس محضر الاستلام",
        )
        self.assertFalse(created_again)
        self.assertEqual(receipt.pk, replay.pk)
        order.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        self.assertEqual(line.received_quantity, Decimal("4.00"))

        receive_purchase_order(
            purchase_order=order,
            received_items=[{"purchase_order_item_id": str(line.pk), "quantity": "6.00"}],
            idempotency_key="stage10-grn-002",
            received_by=self.owner,
            notes="استلام الدفعة الثانية",
        )
        order.refresh_from_db()
        line.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.RECEIVED)
        self.assertEqual(line.received_quantity, Decimal("10.00"))
        self.assertEqual(self.item.current_stock, Decimal("10.00"))
        self.assertEqual(order.receipts.count(), 2)

    def test_vendor_invoice_approval_partial_payment_and_replay(self):
        invoice = VendorInvoice.objects.create(
            school=self.school,
            invoice_number="VINV-ST10-001",
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate(),
            total_amount=Decimal("500.00"),
        )
        invoice, entry = approve_vendor_invoice(invoice=invoice, approved_by=self.owner)
        self.assertEqual(invoice.status, VendorInvoice.Status.APPROVED)
        self.assertEqual(entry.status, "posted")
        self.assertEqual(invoice.approved_by_id, self.owner.pk)

        cash_account = Account.objects.get(school=self.school, code="1101")
        payment_args = {
            "invoice": invoice,
            "payment_account": cash_account,
            "amount": Decimal("200.00"),
            "idempotency_key": "stage10-payment-001",
            "reference_number": "BANK-001",
            "user": self.owner,
        }
        payment_entry, voucher = pay_vendor_invoice(**payment_args)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, VendorInvoice.Status.PARTIAL)
        self.assertEqual(invoice.paid_amount, Decimal("200.00"))
        payment_entry_replay, voucher_replay = pay_vendor_invoice(**payment_args)
        invoice.refresh_from_db()
        self.assertEqual(payment_entry_replay.pk, payment_entry.pk)
        self.assertEqual(voucher_replay.pk, voucher.pk)
        self.assertEqual(invoice.paid_amount, Decimal("200.00"))
        self.assertEqual(VendorInvoicePayment.objects.filter(invoice=invoice).count(), 1)

        pay_vendor_invoice(
            invoice=invoice,
            payment_account=cash_account,
            amount=Decimal("300.00"),
            idempotency_key="stage10-payment-002",
            reference_number="BANK-002",
            user=self.owner,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, VendorInvoice.Status.PAID)
        self.assertEqual(invoice.remaining_amount, Decimal("0.00"))

    def test_fixed_asset_depreciation_is_prorated_and_not_double_posted(self):
        category = AssetCategory.objects.create(
            school=self.school,
            code="EQUIP-ST10",
            name="أجهزة الحاسب",
            annual_depreciation_rate=Decimal("20.00"),
            useful_life_years=5,
        )
        asset = FixedAsset.objects.create(
            school=self.school,
            category=category,
            code="ASSET-ST10-001",
            name="حاسب مختبر",
            purchase_date=date(2026, 1, 1),
            purchase_cost=Decimal("1000.00"),
            salvage_value=Decimal("100.00"),
        )
        depreciation = generate_asset_depreciation(
            asset=asset,
            fiscal_year=self.year,
            posted_by=self.owner,
            post=True,
        )
        self.assertEqual(depreciation.depreciation_amount, Decimal("200.00"))
        self.assertIsNotNone(depreciation.journal_entry_id)
        asset.refresh_from_db()
        self.assertEqual(asset.accumulated_depreciation, Decimal("200.00"))

        replay = generate_asset_depreciation(
            asset=asset,
            fiscal_year=self.year,
            posted_by=self.owner,
            post=True,
        )
        asset.refresh_from_db()
        self.assertEqual(replay.pk, depreciation.pk)
        self.assertEqual(asset.accumulated_depreciation, Decimal("200.00"))
        self.assertEqual(
            AssetDepreciationEntry.objects.filter(asset=asset, fiscal_year=self.year).count(),
            1,
        )

    def test_asset_custody_transfer_and_disposal_create_auditable_entries(self):
        category = AssetCategory.objects.create(
            school=self.school,
            code="FURN-ST10",
            name="أثاث مدرسي",
            annual_depreciation_rate=Decimal("10.00"),
            useful_life_years=10,
        )
        asset = FixedAsset.objects.create(
            school=self.school,
            category=category,
            code="ASSET-ST10-002",
            name="طابعة الإدارة",
            purchase_date=date(2026, 1, 1),
            purchase_cost=Decimal("1000.00"),
            accumulated_depreciation=Decimal("200.00"),
        )
        branch = Branch.objects.create(
            school=self.school,
            code="ST10-BR",
            name="فرع الاختبار",
        )
        movement = move_asset(
            asset=asset,
            idempotency_key="stage10-asset-move",
            reason="نقل الطابعة إلى الفرع",
            to_branch=branch,
            to_location="غرفة الإدارة",
            recorded_by=self.owner,
        )
        self.assertEqual(movement.to_branch_id, branch.pk)
        asset.refresh_from_db()
        self.assertEqual(asset.branch_id, branch.pk)
        replay = move_asset(
            asset=asset,
            idempotency_key="stage10-asset-move",
            reason="إعادة الطلب",
            to_branch=branch,
            to_location="غرفة الإدارة",
            recorded_by=self.owner,
        )
        self.assertEqual(replay.pk, movement.pk)

        cash_account = Account.objects.get(school=self.school, code="1101")
        disposal = dispose_asset(
            asset=asset,
            idempotency_key="stage10-asset-dispose",
            reason="استبدال أصل تجريبي",
            proceeds=Decimal("900.00"),
            payment_account=cash_account,
            disposed_by=self.owner,
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, FixedAsset.Status.DISPOSED)
        self.assertEqual(asset.disposal_journal_entry_id, disposal.journal_entry_id)
        self.assertEqual(disposal.journal_entry.status, "posted")
        self.assertTrue(disposal.journal_entry.lines.filter(account__code="4202", credit=Decimal("100.00")).exists())
        replay_disposal = dispose_asset(
            asset=asset,
            idempotency_key="stage10-asset-dispose",
            reason="إعادة إرسال طلب الاستبعاد",
            proceeds=Decimal("900.00"),
            payment_account=cash_account,
            disposed_by=self.owner,
        )
        self.assertEqual(replay_disposal.pk, disposal.pk)
