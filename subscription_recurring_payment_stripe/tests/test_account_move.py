import logging
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.subscription_recurring_payment_stripe.tests.common import (
    SubscriptionRecurringPaymentStripe,
)

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestAccountMove(SubscriptionRecurringPaymentStripe):
    def setUp(self):
        super().setUp()
        self._setup_test_data()

    def _setup_test_data(self):
        """Setup common test data for all test methods"""
        self.subscription = self.sub1
        self.invoice = self._create_test_invoice()

    def _create_test_invoice(self):
        """Helper method to create a test invoice"""
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.subscription.partner_id.id,
                "invoice_date_due": fields.Date.today(),
                "subscription_id": self.subscription.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_1.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

    def _prepare_payment_method(self):
        """Helper method to prepare payment method data"""
        provider = self.subscription.provider_id
        payment_method = self.env["account.payment.method"].search(
            [("code", "=", provider.code)]
        )
        return self.env["account.payment.method.line"].create(
            {
                "payment_provider_id": provider.id,
                "payment_method_id": payment_method.id,
                "journal_id": self.bank_journal.id,
            }
        )

    def test_01_process_due_invoice_success(self):
        """Test successful processing of a due invoice"""
        self.invoice.action_post()
        method_line = self._prepare_payment_method()

        payment_register = self.env["account.payment.register"]
        payment_vals = {
            "currency_id": self.invoice.currency_id.id,
            "journal_id": self.bank_journal.id,
            "company_id": self.invoice.company_id.id,
            "partner_id": self.invoice.partner_id.id,
            "communication": self.invoice.name,
            "payment_type": "inbound",
            "partner_type": "customer",
            "payment_difference_handling": "open",
            "writeoff_label": "Write-Off",
            "payment_date": fields.Date.today(),
            "amount": self.invoice.amount_total,
            "payment_method_line_id": method_line.id,
            "payment_token_id": self.subscription.payment_token_id.id,
        }

        # Process payment
        payment = payment_register.with_context(
            active_model="account.move",
            active_ids=self.invoice.ids,
            active_id=self.invoice.id,
        ).create(payment_vals)
        payment.action_create_payments()

        self.assertEqual(self.invoice.state, "posted")
        self.assertEqual(self.invoice.payment_state, "paid")

    def test_02_process_due_invoice_no_token(self):
        """Test processing invoice without payment token"""
        self.subscription.payment_token_id = False

        self.env["account.move"].cron_process_due_invoices()

        self.assertEqual(self.invoice.state, "draft")

    def test_03_process_due_invoice_invalid_state(self):
        """Test processing invoice in invalid state"""
        self.invoice.state = "cancel"

        self.env["account.move"].cron_process_due_invoices()
        self.assertEqual(self.invoice.payment_state, "not_paid")

    @patch(  # noqa: B950
        "odoo.addons.payment_stripe.models.payment_provider.PaymentProvider._stripe_make_request"  # noqa: B950
    )
    def test_04_process_due_invoice_stripe_error(self, mock_stripe):
        """Test handling of Stripe API errors"""
        mock_stripe.side_effect = ValidationError("Stripe API Error")

        self.env["account.move"].cron_process_due_invoices()

        self.assertEqual(self.invoice.payment_state, "not_paid")

    def test_05_process_multiple_due_invoices(self):
        """Test processing multiple due invoices"""
        # Create second invoice
        invoice2 = self._create_test_invoice()
        invoice2.invoice_date_due = fields.Date.today() - timedelta(days=1)

        invoices = self.invoice | invoice2
        invoices.action_post()

        self.env["account.move"].cron_process_due_invoices()

        for inv in invoices:
            self.assertEqual(inv.state, "posted")
