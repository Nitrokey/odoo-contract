import logging

import stripe

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_register_payment(self):
        """
        Override `action_register_payment` to automatically process Stripe
        payment on subscriptions.
        """
        for invoice in self:
            # Find the subscription associated with the invoice, if it exists
            subscription = invoice.subscription_id

            # Check if the subscription is recurring and has a payment method
            if subscription and subscription.charge_automatically:
                provider = subscription.provider_id
                stripe.api_key = provider.stripe_secret_key
                token = self._create_token(subscription)
                try:
                    # Create the PaymentIntent and confirm it immediately
                    payment_intent = stripe.PaymentIntent.create(
                        # Stripe uses cents
                        amount=int(invoice.amount_total * 100),
                        currency=invoice.currency_id.name.lower(),
                        customer=token.provider_ref,
                        payment_method=token.stripe_payment_method,
                        automatic_payment_methods={"enabled": True},
                        # For automatic payments without user intervention
                        off_session=True,
                        # Confirm the PaymentIntent immediately
                        confirm=True,
                        metadata={"odoo_invoice_id": str(invoice.id)},
                    )

                    # Handling the result of the PaymentIntent
                    if payment_intent["status"] != "succeeded":
                        raise UserError(
                            _("Payment failed with status: %s")
                            % payment_intent["status"]
                        )

                    # If the payment is successful, record the payment on
                    # the invoice
                    Payment = self.env["account.payment"].sudo()
                    payment_vals = {
                        "journal_id": self.env["account.journal"]
                        .search([("type", "=", "bank")], limit=1)
                        .id,
                        "amount": invoice.amount_total,
                        "payment_type": "inbound",
                        "partner_type": "customer",
                        "partner_id": invoice.partner_id.id,
                        "payment_method_id": self.env.ref(
                            "account.account_payment_method_manual_in"
                        ).id,
                        "ref": f"Stripe - {payment_intent['id']}",
                    }
                    payment = Payment.create(payment_vals)
                    payment.action_post()
                    invoice.payment_state = "paid"

                except stripe.StripeError as e:
                    raise UserError(f"Stripe error: {e}") from e

            else:
                return super(AccountMove, self).action_register_payment()

    def _create_token(self, subscription):
        provider = subscription.provider_id
        # Search for an existing payment token for the given provider and
        # partner
        token = self.env["payment.token"].search(
            [
                ("provider_id", "=", provider.id),
                ("partner_id", "=", subscription.partner_id.id),
            ],
            limit=1,
        )

        # If no token exists, create a new one
        if not token:
            stripe.api_key = provider.stripe_secret_key

            # Create a new Stripe customer
            customer = stripe.Customer.create(
                email=subscription.partner_id.email,
                name=subscription.partner_id.name,
                metadata={"odoo_subscription": str(subscription.name)},
            )

            # Create a new payment token in Odoo
            new_token = self.env["payment.token"].create(
                {
                    "provider_id": provider.id,
                    "partner_id": subscription.partner_id.id,
                    "provider_ref": customer.id,
                    "verified": True,
                }
            )

            # Retrieve the default payment method for the customer,
            # or create one if it doesn't exist
            new_token.stripe_payment_method = (
                stripe.PaymentMethod.list(
                    customer=customer.id,
                    type="card",
                    limit=1,
                )
                .data[0]
                .id
                if stripe.PaymentMethod.list(
                    customer=customer.id, type="card", limit=1
                ).data
                else stripe.Customer.create_source(
                    customer.id,
                    source="tok_visa",
                ).id
            )

            # Assign the new token to the variable
            token = new_token

        return token

    @api.model
    def cron_process_due_invoices(self):
        """Process payment of overdue invoices for recurring subscriptions."""

        for invoice in self:
            # Find the subscription associated with the invoice
            subscription = invoice.subscription_id

            # Check if it's a recurring subscription with Stripe
            if subscription and subscription.charge_automatically:
                try:
                    # Register the payment
                    invoice.action_post()
                    invoice.action_register_payment()
                except Exception as e:
                    _logger.error(f"Error Processing Due Invoices: {str(e)}")
