from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.auditlog.models import AuditEvent
from apps.platform.models import Plan, PlatformInvoice, Subscription
from apps.platform.services import record_successful_platform_payment
from apps.tenants.models import School


class PlatformBillingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+967777000003", password="Strong-Password-03",
            first_name="محمد", last_name="المالك", email="platform-owner@example.test",
        )
        cls.school = School.objects.create(owner=cls.owner, code="BILL01", name="مدرسة الحساب")
        cls.plan = Plan.objects.create(code="standard", name="الباقة القياسية", price=Decimal("100.00"), currency_code="YER")
        now = timezone.now()
        cls.subscription = Subscription.objects.create(
            school=cls.school, plan=cls.plan,
            starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=365),
            status=Subscription.Status.ACTIVE, price_locked=Decimal("100.00"), currency_code="YER",
        )
        cls.invoice = PlatformInvoice.objects.create(
            school=cls.school, subscription=cls.subscription, number="PLAT-0001",
            status=PlatformInvoice.Status.ISSUED, issue_date=date.today(), due_date=date.today() + timedelta(days=15),
            subtotal=Decimal("100.00"), discount_amount=Decimal("0.00"), tax_amount=Decimal("0.00"),
            total=Decimal("100.00"), currency_code="YER",
        )

    def test_platform_payment_updates_only_platform_invoice(self):
        payment = record_successful_platform_payment(
            invoice_id=self.invoice.pk, amount="40.00", method="bank_transfer", actor=self.owner,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, payment.Status.SUCCEEDED)
        self.assertEqual(self.invoice.paid_amount, Decimal("40.00"))
        self.assertEqual(self.invoice.status, PlatformInvoice.Status.PARTIAL)

    def test_invoice_rejects_cross_school_subscription(self):
        other_school = School.objects.create(owner=self.owner, code="BILL02", name="مدرسة أخرى")
        invoice = PlatformInvoice(
            school=other_school, subscription=self.subscription, number="PLAT-0002",
            issue_date=date.today(), due_date=date.today() + timedelta(days=1),
            subtotal=Decimal("100"), total=Decimal("100"), currency_code="YER",
        )
        with self.assertRaises(ValidationError):
            invoice.full_clean()

    def test_audit_event_cannot_be_changed_or_deleted(self):
        event = AuditEvent.objects.create(
            school=self.school, actor=self.owner, action="test.created",
            description="حدث اختبار", occurred_at=timezone.now(),
        )
        event.description = "تغيير غير مسموح"
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            event.delete()
        with self.assertRaises(ValueError):
            AuditEvent.objects.filter(pk=event.pk).update(description="تعديل جماعي")
        with self.assertRaises(ValueError):
            AuditEvent.objects.filter(pk=event.pk).delete()
