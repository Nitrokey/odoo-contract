import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def cron_process_due_invoices(self):
        """Process payment of overdue invoices for recurring subscriptions."""

        for invoice in self.search(
            [
                ("state", "in", ["draft"]),
                ("invoice_date_due", "<=", fields.Date.today()),
            ]
        ).filtered(lambda inv: inv.subscription_id):
            # Find the subscription associated with the invoice
            subscription = invoice.subscription_id

            # Check if it's a recurring subscription with Stripe
            if (
                subscription
                and subscription.charge_automatically
                and subscription.payment_token_id
            ):
                try:
                    # Post the invoice
                    invoice.action_post()

                    # Prepare payment data
                    provider = invoice.subscription_id.provider_id
                    method_line = self.env["account.payment.method.line"].search(
                        [("payment_method_id.code", "=", provider.code)],
                        limit=1,
                    )
                    journal = self.env["account.journal"].search(
                        [
                            ("type", "in", ("bank", "cash")),
                            ("company_id", "=", invoice.company_id.id),
                        ],
                        limit=1,
                    )

                    payment_register = self.env["account.payment.register"]

                    payment_vals = {
                        "currency_id": invoice.currency_id.id,
                        "journal_id": journal.id,
                        "company_id": invoice.company_id.id,
                        "partner_id": invoice.partner_id.id,
                        "communication": invoice.name,
                        "payment_type": "inbound",
                        "partner_type": "customer",
                        "payment_difference_handling": "open",
                        "writeoff_label": "Write-Off",
                        "payment_date": fields.Date.today(),
                        "amount": invoice.amount_total,
                        "payment_method_line_id": method_line.id,
                        "payment_token_id": subscription.payment_token_id.id,
                    }
                    # Create payment and pay the invoice
                    payment_register.with_context(
                        active_model="account.move",
                        active_ids=invoice.ids,
                        active_id=invoice.id,
                    ).create(payment_vals).action_create_payments()
                    _logger.info(f"Processed Due Invoice: {invoice.name}")
                except Exception as e:
                    _logger.error(f"Error Processing Due Invoices: {str(e)}")
