import uuid

import stripe

from odoo import fields
from odoo.tests.common import TransactionCase


class TestPaymentStripeRecurring(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["payment.provider"].create(
            {
                "name": "Stripe",
                "code": "stripe",
                "stripe_secret_key": "sk_test_4eC39HqLyjWDarjtT1zdp7dc",
            }
        )
        cls.sale_journal = cls.env["account.journal"].search(
            [
                ("type", "=", "sale"),
                ("company_id", "=", cls.env.ref("base.main_company").id),
            ]
        )[0]
        cls.pricelist1 = cls.env["product.pricelist"].create(
            {
                "name": "pricelist for contract test",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "test@example.com",
                "property_product_pricelist": cls.pricelist1.id,
            }
        )
        cls.tax_10pc_incl = cls.env["account.tax"].create(
            {
                "name": "10% Tax incl",
                "amount_type": "percent",
                "amount": 10,
                "price_include": True,
            }
        )
        cls.country = cls.env["res.country"].search([], limit=1)
        cls.fiscal = cls.env["account.fiscal.position"].create(
            {
                "name": "Regime National",
                "auto_apply": True,
                "country_id": cls.country.id,
                "vat_required": True,
                "sequence": 10,
            }
        )
        cls.product_1 = cls.env.ref("product.product_product_1")
        cls.product_1.subscribable = True
        cls.product_1.taxes_id = [(6, 0, cls.tax_10pc_incl.ids)]
        cls.product_2 = cls.env.ref("product.product_product_2")
        cls.product_2.subscribable = True
        cls.pricelist2 = cls.env["product.pricelist"].create(
            {
                "name": "pricelist for contract test 2",
                "discount_policy": "with_discount",
            }
        )
        cls.tmpl2 = cls.create_sub_template(
            {
                "recurring_rule_boundary": "limited",
                "recurring_rule_type": "days",
            }
        )
        cls.tag = cls.env["sale.subscription.tag"].create(
            {
                "name": "Test Tag",
            }
        )
        cls.stage = cls.env["sale.subscription.stage"].create(
            {
                "name": "Test Sub Stage",
            }
        )
        cls.sub8 = cls.create_sub(
            {
                "partner_id": cls.partner.id,
                "template_id": cls.tmpl2.id,
                "pricelist_id": cls.pricelist2.id,
                "date_start": fields.Date.today(),
                "in_progress": True,
                "journal_id": cls.sale_journal.id,
                "company_id": 1,
                "tag_ids": [(6, 0, [cls.tag.id])],
                "stage_id": cls.stage.id,
                "fiscal_position_id": cls.fiscal.id,
                "charge_automatically": True,
                "provider_id": cls.provider.id,
            }
        )

        cls.invoice = cls.env["account.move"].create(
            {
                "partner_id": cls.partner.id,
                "move_type": "out_invoice",
                "invoice_line_ids": [
                    (
                        0,
                        None,
                        {
                            "product_id": cls.product_2.id,
                            "quantity": 3,
                            "price_unit": 750,
                        },
                    ),
                ],
                "subscription_id": cls.sub8.id,
            }
        )

    @classmethod
    def create_sub_template(cls, vals):
        code = str(uuid.uuid4().hex)
        default_vals = {
            "name": "Test Template " + code,
            "code": code,
            "description": "Some sort of subscription terms",
            "product_ids": [(6, 0, [cls.product_1.id, cls.product_2.id])],
        }
        default_vals.update(vals)
        rec = cls.env["sale.subscription.template"].create(default_vals)
        return rec

    @classmethod
    def create_sub(cls, vals):
        default_vals = {
            "company_id": 1,
            "partner_id": cls.partner.id,
            "template_id": cls.tmpl2.id,
            "tag_ids": [(6, 0, [cls.tag.id])],
            "stage_id": cls.stage.id,
            "pricelist_id": cls.pricelist1.id,
            "fiscal_position_id": cls.fiscal.id,
            "charge_automatically": True,
        }
        default_vals.update(vals)
        rec = cls.env["sale.subscription"].create(default_vals)
        return rec

    def test_action_register_payment(self):
        self.assertTrue(
            self.invoice.state == "draft",
            f"Invoice {self.invoice.id} should be in draft state",
        )

        self.invoice.cron_process_due_invoices()

        self.assertTrue(
            self.invoice.state == "posted",
            f"Invoice {self.invoice.id} should be posted",
        )
        self.assertTrue(
            self.invoice.payment_state == "paid",
            f"Invoice {self.invoice.id} should be paid",
        )

    def test_stripe_payment_intent(self):
        stripe.api_key = self.provider.stripe_secret_key
        provider = self.sub8.provider_id
        stripe.api_key = provider.stripe_secret_key
        token = self.invoice._create_token(self.sub8)

        payment_intent = stripe.PaymentIntent.create(
            # Stripe uses cents
            amount=int(self.invoice.amount_total * 100),
            currency=self.invoice.currency_id.name.lower(),
            customer=token.provider_ref,
            payment_method=token.stripe_payment_method,
            automatic_payment_methods={"enabled": True},
            # For automatic payments without user intervention
            off_session=True,
            # Confirm the PaymentIntent immediately
            confirm=True,
            metadata={"odoo_invoice_id": str(self.invoice.id)},
        )

        # Check if the payment was successful
        self.assertEqual(payment_intent.status, "succeeded")
