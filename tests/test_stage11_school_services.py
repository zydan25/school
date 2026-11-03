"""Regression tests for Stage 11 optional school services."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import Resolver404, resolve
from django.utils import timezone

from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.accounting.models import FiscalPeriod, FiscalYear
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounts.models import User
from apps.accounts.services import is_school_permission_codename_allowed
from apps.inventory.models import InventoryItem, StockMovement, Warehouse
from apps.platform.models import Feature, Plan, PlanFeature, Subscription
from apps.school_services.api import serializers as service_serializers
from apps.school_services.models import (
    BookLoan,
    BookRequisitionFulfillment,
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusRoute,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
)
from apps.school_services.services import (
    fulfill_book_requisition,
    issue_bus_route_monthly_invoices,
    mark_book_loan_lost,
    renew_book_loan,
    return_book_loan,
    school_service_feature_state,
    school_service_is_enabled,
    set_school_service_enabled,
)
from apps.students.models import Student
from apps.tenants.models import School, SchoolSettings
from apps.tenants.services import provision_school


class Stage11SchoolServicesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+967770001101",
            password="StrongPassword123!",
            first_name="اختبار",
            last_name="المرحلة الحادية عشرة",
        )
        self.school = School.objects.create(
            owner=self.owner,
            name="مدرسة خدمات المرحلة الحادية عشرة",
            code="STAGE11",
            status=School.Status.ACTIVE,
        )
        provision_school(self.school)
        self.settings, _ = SchoolSettings.objects.get_or_create(school=self.school)

        self.academic_year = AcademicYear.objects.create(
            school=self.school,
            name="السنة الدراسية 2026-2027",
            code="AY-2026-2027",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30),
            status=AcademicYear.Status.ACTIVE,
            is_current=True,
        )
        self.stage = EducationalStage.objects.create(
            school=self.school,
            name="المرحلة الأساسية",
            code="STAGE-BASIC",
            sequence=1,
        )
        self.grade = GradeLevel.objects.create(
            school=self.school,
            stage=self.stage,
            name="الصف الثالث",
            code="G-3",
            sequence=3,
        )
        self.section = Section.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            grade=self.grade,
            code="SEC-A",
            name="الشعبة أ",
        )
        self.student = Student.objects.create(
            school=self.school,
            student_id_number="ST11-0001",
            first_name="طالب",
            last_name="اختبار",
            grade_level=self.grade,
            section=self.section,
            academic_year=self.academic_year,
        )

        self.fiscal_year = FiscalYear.objects.create(
            school=self.school,
            name="السنة المالية 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        FiscalPeriod.objects.create(
            school=self.school,
            fiscal_year=self.fiscal_year,
            period_number=1,
            name="الفترة السنوية للاختبار",
            start_date=self.fiscal_year.start_date,
            end_date=self.fiscal_year.end_date,
        )
        seed_default_chart_of_accounts(self.school)

    def test_library_loan_renews_returns_and_posts_a_single_overdue_fine(self):
        self.settings.library_default_loan_days = 14
        self.settings.library_max_renewals = 2
        self.settings.library_overdue_fine_per_day = Decimal("2.00")
        self.settings.library_max_overdue_fine = Decimal("10.00")
        self.settings.save()

        book = LibraryBook.objects.create(
            school=self.school,
            title="مبادئ العلوم",
            author="مؤلف تجريبي",
            total_copies=2,
            available_copies=2,
        )
        loan = BookLoan.objects.create(
            school=self.school,
            book=book,
            student=self.student,
            borrow_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=1),
        )
        book.refresh_from_db()
        self.assertEqual(book.available_copies, 1)

        renewed = renew_book_loan(school=self.school, loan_id=loan.pk, actor=self.owner)
        self.assertEqual(renewed.renewal_count, 1)
        self.assertEqual(
            renewed.due_date,
            timezone.localdate() + timedelta(days=15),
        )
        with self.assertRaises(ValidationError):
            loan.due_date = timezone.localdate() + timedelta(days=20)
            loan.save(update_fields=["due_date", "updated_at"])

        loan.status = BookLoan.Status.RETURNED
        loan.return_date = timezone.localdate()
        with self.assertRaises(ValidationError):
            loan.save(update_fields=["status", "return_date", "updated_at"])
        returned_first = return_book_loan(
            school=self.school, loan_id=loan.pk, actor=self.owner
        )
        self.assertEqual(returned_first.status, BookLoan.Status.RETURNED)
        self.assertEqual(returned_first.fine_amount, Decimal("0.00"))

        overdue_loan = BookLoan.objects.create(
            school=self.school,
            book=book,
            student=self.student,
            borrow_date=timezone.localdate() - timedelta(days=20),
            due_date=timezone.localdate() - timedelta(days=8),
        )
        returned = return_book_loan(
            school=self.school, loan_id=overdue_loan.pk, actor=self.owner
        )
        self.assertEqual(returned.status, BookLoan.Status.RETURNED)
        self.assertEqual(returned.fine_amount, Decimal("10.00"))
        self.assertIsNotNone(returned.fine_invoice_id)
        self.assertEqual(returned.fine_invoice.status, returned.fine_invoice.Status.UNPAID)
        self.assertEqual(
            returned.fine_invoice.journal_entry.status,
            returned.fine_invoice.journal_entry.Status.POSTED,
        )
        repeated = return_book_loan(
            school=self.school, loan_id=overdue_loan.pk, actor=self.owner
        )
        self.assertEqual(repeated.fine_invoice_id, returned.fine_invoice_id)
        book.refresh_from_db()
        self.assertEqual(book.available_copies, 2)

    def test_lost_library_book_is_fined_once_and_cannot_be_returned(self):
        self.settings.library_lost_book_fine = Decimal("25.00")
        self.settings.save()
        book = LibraryBook.objects.create(
            school=self.school,
            title="مرجع مفقود",
            total_copies=1,
            available_copies=1,
        )
        loan = BookLoan.objects.create(
            school=self.school,
            book=book,
            student=self.student,
            due_date=timezone.localdate() + timedelta(days=7),
        )
        lost = mark_book_loan_lost(
            school=self.school, loan_id=loan.pk, actor=self.owner
        )
        repeated = mark_book_loan_lost(
            school=self.school, loan_id=loan.pk, actor=self.owner
        )
        self.assertEqual(lost.status, BookLoan.Status.LOST)
        self.assertEqual(repeated.fine_invoice_id, lost.fine_invoice_id)
        self.assertEqual(lost.fine_amount, Decimal("25.00"))
        with self.assertRaises(ValidationError):
            return_book_loan(school=self.school, loan_id=loan.pk, actor=self.owner)
        book.refresh_from_db()
        self.assertEqual(book.available_copies, 0)

    def test_transport_monthly_invoice_is_linked_to_one_charge_and_one_journal(self):
        route = BusRoute.objects.create(
            school=self.school,
            route_name="الخط الشمالي",
            route_code="BUS-N",
            bus_number="BUS-11",
            bus_capacity=20,
            driver_name="سائق تجريبي",
            driver_phone="770000011",
            monthly_fee=Decimal("100.00"),
            contract_amount=Decimal("800.00"),
        )
        subscription = StudentBusSubscription.objects.create(
            school=self.school,
            student=self.student,
            bus_route=route,
            academic_year=self.academic_year,
        )

        first = issue_bus_route_monthly_invoices(
            school=self.school,
            route_id=route.pk,
            year=2026,
            month=11,
            actor=self.owner,
        )
        replay = issue_bus_route_monthly_invoices(
            school=self.school,
            route_id=route.pk,
            year=2026,
            month=11,
            actor=self.owner,
        )
        self.assertEqual(first["created"], 1)
        self.assertEqual(first["already_issued"], 0)
        self.assertEqual(replay["created"], 0)
        self.assertEqual(replay["already_issued"], 1)
        self.assertEqual(first["charges"][0].subscription_id, subscription.pk)
        self.assertEqual(first["charges"][0].amount, Decimal("100.00"))
        self.assertEqual(first["charges"][0].invoice.total_amount, Decimal("100.00"))
        self.assertIsNotNone(first["charges"][0].invoice.journal_entry_id)
        self.assertEqual(
            first["charges"][0].invoice.journal_entry.status,
            first["charges"][0].invoice.journal_entry.Status.POSTED,
        )

    def test_bus_subscription_capacity_is_enforced_and_settlement_is_tenant_scoped(self):
        route = BusRoute.objects.create(
            school=self.school,
            route_name="خط محدود المقاعد",
            route_code="BUS-CAP",
            bus_number="BUS-12",
            bus_capacity=1,
            driver_name="سائق",
            driver_phone="770000012",
            monthly_fee=Decimal("50.00"),
            contract_amount=Decimal("500.00"),
        )
        StudentBusSubscription.objects.create(
            school=self.school,
            student=self.student,
            bus_route=route,
            academic_year=self.academic_year,
        )
        second_student = Student.objects.create(
            school=self.school,
            student_id_number="ST11-0002",
            first_name="طالب",
            last_name="ثان",
            grade_level=self.grade,
            section=self.section,
            academic_year=self.academic_year,
        )
        with self.assertRaises(ValidationError):
            StudentBusSubscription.objects.create(
                school=self.school,
                student=second_student,
                bus_route=route,
                academic_year=self.academic_year,
            )

        settlement = BusFinancialSettlement.objects.create(
            school=self.school,
            bus_route=route,
            academic_year=self.academic_year,
            month=11,
            year=2026,
        )
        settlement.calculate_due()
        self.assertEqual(settlement.student_count, 1)
        self.assertEqual(settlement.gross_due, Decimal("500.00"))
        voucher = settlement.approve_and_create_payment_voucher(
            approved_by_user=self.owner
        )
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, BusFinancialSettlement.Status.PAID)
        self.assertIsNotNone(settlement.payment_voucher_id)
        self.assertEqual(voucher.status, voucher.Status.POSTED)
        self.assertIsNotNone(voucher.journal_entry_id)

    def test_book_requisition_fulfilment_is_stock_linked_and_idempotent(self):
        warehouse = Warehouse.objects.create(
            school=self.school,
            code="WH-11",
            name="مستودع الاختبار",
        )
        item = InventoryItem.objects.create(
            school=self.school,
            code="BOOK-11",
            name="كتاب العلوم",
            warehouse=warehouse,
            unit=InventoryItem.Unit.BOOK,
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("15.00"),
            reorder_level=Decimal("1.00"),
        )
        order = BookRequisitionOrder.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            grade_level=self.grade,
            section=self.section,
            requested_by=self.owner,
            status=BookRequisitionOrder.Status.DRAFT,
            order_number="REQ-ST11-001",
        )
        line = BookRequisitionItem.objects.create(
            school=self.school,
            requisition=order,
            book_title="كتاب العلوم",
            quantity_requested=5,
        )
        line.quantity_approved = 5
        line._allow_requisition_approval_update = True
        line.save(update_fields=["quantity_approved", "updated_at"])
        order.status = BookRequisitionOrder.Status.APPROVED
        order._allow_requisition_workflow_update = True
        order.save(update_fields=["status", "updated_at"])
        allocation = [{
            "requisition_item_id": str(line.pk),
            "inventory_item_id": str(item.pk),
            "quantity": 2,
        }]
        first = fulfill_book_requisition(
            school=self.school,
            order_id=order.pk,
            allocations=allocation,
            idempotency_key="stage11-fulfil-001",
            actor=self.owner,
        )
        replay = fulfill_book_requisition(
            school=self.school,
            order_id=order.pk,
            allocations=allocation,
            idempotency_key="stage11-fulfil-001",
            actor=self.owner,
        )
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(
            BookRequisitionFulfillment.objects.filter(
                school=self.school,
                idempotency_key="stage11-fulfil-001",
            ).count(),
            1,
        )
        self.assertEqual(StockMovement.objects.filter(
            school=self.school,
            reference=order.order_number,
            movement_type=StockMovement.MovementType.ISSUE,
        ).count(), 1)

        second_allocation = [{
            "requisition_item_id": str(line.pk),
            "inventory_item_id": str(item.pk),
            "quantity": 3,
        }]
        fulfill_book_requisition(
            school=self.school,
            order_id=order.pk,
            allocations=second_allocation,
            idempotency_key="stage11-fulfil-002",
            actor=self.owner,
        )
        order.refresh_from_db()
        line.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.status, BookRequisitionOrder.Status.FULFILLED)
        self.assertEqual(line.quantity_dispatched, 5)
        self.assertEqual(item.current_stock, Decimal("5.00"))

    def test_book_distribution_uses_stock_ledger_for_delivery_and_return(self):
        warehouse = Warehouse.objects.create(
            school=self.school,
            code="WH-DIST",
            name="مستودع التوزيع",
        )
        item = InventoryItem.objects.create(
            school=self.school,
            code="BOOK-DIST",
            name="كتاب اللغة العربية",
            warehouse=warehouse,
            unit=InventoryItem.Unit.BOOK,
            current_stock=Decimal("5.00"),
            unit_cost=Decimal("12.00"),
        )
        distribution = StudentBookDistribution.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            inventory_item=item,
            book_title="كتاب اللغة العربية",
            quantity=Decimal("2.00"),
            fee_amount=Decimal("0.00"),
        )
        distribution.deliver_book(user=self.owner)
        distribution.refresh_from_db()
        self.assertEqual(distribution.delivery_status, StudentBookDistribution.DeliveryStatus.DELIVERED)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("3.00"))
        distribution.return_book(user=self.owner)
        distribution.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(distribution.delivery_status, StudentBookDistribution.DeliveryStatus.RETURNED)
        self.assertEqual(item.current_stock, Decimal("5.00"))
        self.assertEqual(
            StockMovement.objects.filter(school=self.school, reference__icontains="ST11-0001").count(),
            2,
        )

    def test_optional_features_require_subscription_entitlement_and_can_be_disabled_locally(self):
        feature, _ = Feature.objects.get_or_create(
            code="school-transport",
            defaults={
                "name": "النقل المدرسي",
                "module_key": "school_services",
                "is_active": True,
                "is_addon": True,
            },
        )
        plan = Plan.objects.create(
            code="stage11-test",
            name="باقة الاختبار",
            price=Decimal("1000.00"),
            currency_code="YER",
            max_branches=1,
        )
        PlanFeature.objects.create(plan=plan, feature=feature, is_included=True)
        now = timezone.now()
        Subscription.objects.create(
            school=self.school,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
            price_locked=plan.price,
            currency_code=plan.currency_code,
        )
        self.assertTrue(school_service_is_enabled(self.school, "school-transport"))
        disabled = set_school_service_enabled(
            school=self.school,
            feature_code="school-transport",
            enabled=False,
            actor=self.owner,
        )
        self.assertFalse(disabled["enabled"])
        self.assertFalse(school_service_is_enabled(self.school, "school-transport"))
        enabled = set_school_service_enabled(
            school=self.school,
            feature_code="school-transport",
            enabled=True,
            actor=self.owner,
        )
        self.assertTrue(enabled["enabled"])
        self.assertTrue(school_service_is_enabled(self.school, "school-transport"))
        state = school_service_feature_state(self.school)
        self.assertEqual(
            next(row["code"] for row in state if row["enabled"]),
            "school-transport",
        )


class Stage11SchoolServicesContractTests(TestCase):
    def test_clinic_permissions_are_not_assignable_or_authorized(self):
        for action in ("view", "add", "change", "delete"):
            for model_name in ("clinicvisit", "studenthealthprofile"):
                with self.subTest(action=action, model=model_name):
                    self.assertFalse(
                        is_school_permission_codename_allowed(
                            "school_services", f"{action}_{model_name}"
                        )
                    )

    def test_optional_service_api_routes_exist_without_any_clinic_route(self):
        routes = {
            "/api/v1/school-services/features/": "school-service-features",
            "/api/v1/school-services/library/policy/": "school-library-policy",
            "/api/v1/school-services/bus-routes/": "school-bus-route-list",
            "/api/v1/school-services/bus-subscriptions/": "school-bus-subscription-list",
            "/api/v1/school-services/bus-charges/": "school-bus-charge-list",
            "/api/v1/school-services/library/books/": "school-library-book-list",
            "/api/v1/school-services/library/loans/": "school-library-loan-list",
            "/api/v1/school-services/bus-settlements/": "school-bus-settlement-list",
            "/api/v1/school-services/book-distributions/": "school-book-distribution-list",
            "/api/v1/school-services/book-requisitions/": "school-book-requisition-list",
        }
        for path, name in routes.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, name)

        for path in (
            "/api/v1/school-services/clinic/health-profiles/",
            "/api/v1/school-services/clinic/visits/",
        ):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)

    def test_existing_app_owned_api_routes_remain_canonical(self):
        existing = {
            "/api/v1/students/": "student-list",
            "/api/v1/staff/members/": "staff-list",
            "/api/v1/fees/invoices/": "invoice-list-create",
            "/api/v1/payroll/runs/": "payroll-run-list",
            "/api/v1/attendance/registers/": "attendance-register-list",
            "/api/v1/notifications/": "user-notifications",
            "/api/v1/timetable/ai-generate/": "ai-generate",
        }
        for path, name in existing.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, name)

    def test_available_optional_service_serializers_have_valid_fields(self):
        serializer_types = (
            service_serializers.BusRouteSerializer,
            service_serializers.StudentBusSubscriptionSerializer,
            service_serializers.BusSubscriptionChargeSerializer,
            service_serializers.LibraryBookSerializer,
            service_serializers.BookLoanSerializer,
            service_serializers.BusFinancialSettlementSerializer,
            service_serializers.StudentBookDistributionSerializer,
            service_serializers.BookRequisitionItemSerializer,
            service_serializers.BookRequisitionOrderSerializer,
        )
        errors = {}
        for serializer_type in serializer_types:
            try:
                tuple(serializer_type().fields.keys())
            except Exception as exc:
                errors[serializer_type.__name__] = f"{type(exc).__name__}: {exc}"
        self.assertEqual(errors, {})
