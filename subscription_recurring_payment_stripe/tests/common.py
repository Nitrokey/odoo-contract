import uuid

from dateutil.relativedelta import relativedelta

from odoo import fields

from odoo.addons.payment_stripe.tests.common import StripeCommon


class SubscriptionRecurringPaymentStripe(StripeCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.portal_user = cls.env.ref("base.demo_user0")
        cls.cash_journal = cls.env["account.journal"].search(
            [
                ("type", "=", "cash"),
                ("company_id", "=", cls.env.ref("base.main_company").id),
            ]
        )[0]
        cls.bank_journal = cls.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("company_id", "=", cls.env.ref("base.main_company").id),
            ]
        )[0]
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
        cls.pricelist2 = cls.env["product.pricelist"].create(
            {
                "name": "pricelist for contract test 2",
                "discount_policy": "with_discount",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "partner test subscription_oca",
                "property_product_pricelist": cls.pricelist1.id,
                "email": "demo1@demo.com",
            }
        )
        cls.partner_2 = cls.env["res.partner"].create(
            {
                "name": "partner test subscription_oca 2",
                "property_product_pricelist": cls.pricelist1.id,
                "email": "demo2@demo.com",
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
        cls.product_1 = cls.env.ref("product.product_product_1")
        cls.product_1.subscribable = True
        cls.product_1.taxes_id = [(6, 0, cls.tax_10pc_incl.ids)]
        cls.product_2 = cls.env.ref("product.product_product_2")
        cls.product_2.subscribable = True

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

        cls.tmpl1 = cls.create_sub_template({})
        cls.tmpl2 = cls.create_sub_template(
            {
                "recurring_rule_boundary": "limited",
                "recurring_rule_type": "days",
            }
        )
        cls.tmpl3 = cls.create_sub_template(
            {
                "recurring_rule_boundary": "unlimited",
                "recurring_rule_type": "weeks",
            }
        )
        cls.tmpl4 = cls.create_sub_template(
            {
                "recurring_rule_boundary": "limited",
                "invoicing_mode": "invoice",
                "recurring_rule_type": "years",
            }
        )
        cls.tmpl5 = cls.create_sub_template(
            {
                "recurring_rule_boundary": "unlimited",
                "invoicing_mode": "invoice",
                "recurring_rule_type": "days",
            }
        )

        cls.stage = cls.env["sale.subscription.stage"].create(
            {
                "name": "Test Sub Stage",
            }
        )
        cls.stage_2 = cls.env["sale.subscription.stage"].create(
            {
                "name": "Test Sub Stage 2",
                "type": "pre",
            }
        )
        cls.tag = cls.env["sale.subscription.tag"].create(
            {
                "name": "Test Tag",
            }
        )

        cls.stripe = cls._prepare_provider(
            "stripe",
            update_values={
                "stripe_secret_key": "sk_test_KJtHgNwt2KS3xM7QJPr4O5E8",
                "stripe_publishable_key": "pk_test_QSPnimmb4ZhtkEy3Uhdm4S6J",
                "stripe_webhook_secret": "whsec_vG1fL6CMUouQ7cObF2VJprLVXT5jBLxB",
                "payment_icon_ids": [(5, 0, 0)],
            },
        )

        cls.provider = cls.stripe
        cls.token = cls.env["payment.token"].create(
            {
                "provider_id": cls.stripe.id,
                "partner_id": cls.env.ref("base.res_partner_1").id,
                "company_id": cls.env.ref("base.main_company").id,
                "payment_details": "4242",
                "provider_ref": "cus_LBxMCDggAFOiNR",
            }
        )

        cls.sub1 = cls.create_sub(
            {
                "template_id": cls.tmpl2.id,
                "pricelist_id": cls.pricelist2.id,
                "date_start": fields.Date.today() - relativedelta(days=100),
                "in_progress": True,
                "journal_id": cls.bank_journal.id,
                "charge_automatically": True,
                "provider_id": cls.stripe.id,
                "payment_token_id": cls.token.id,
            }
        )

        cls.sub_line = cls.create_sub_line(cls.sub1)
        cls.sub_line2 = cls.env["sale.subscription.line"].create(
            {
                "company_id": 1,
                "sale_subscription_id": cls.sub1.id,
            }
        )

        cls.close_reason = cls.env["sale.subscription.close.reason"].create(
            {
                "name": "Test Close Reason",
            }
        )
        cls.sub_line2.read(["name", "price_unit"])
        cls.sub_line2.unlink()

        # Pricelists.
        cls.pricelist_default = cls.env.ref("product.list0")
        cls.pricelist_l1 = cls._create_price_list("Level 1")
        cls.pricelist_l2 = cls._create_price_list("Level 2")
        cls.pricelist_l3 = cls._create_price_list("Level 3")
        cls.env["product.pricelist.item"].create(
            {
                "pricelist_id": cls.pricelist_l3.id,
                "applied_on": "0_product_variant",
                "compute_price": "formula",
                "base": "pricelist",
                "base_pricelist_id": cls.pricelist_l1.id,
                "product_id": cls.product_1.id,
            }
        )
        cls.env["product.pricelist.item"].create(
            {
                "pricelist_id": cls.pricelist_l2.id,
                "applied_on": "3_global",
                "compute_price": "formula",
                "base": "pricelist",
                "base_pricelist_id": cls.pricelist_l1.id,
            }
        )
        cls.env["product.pricelist.item"].create(
            {
                "pricelist_id": cls.pricelist_l1.id,
                "applied_on": "3_global",
                "compute_price": "formula",
                "base": "standard_price",
                "fixed_price": 1000,
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
            "template_id": cls.tmpl1.id,
            "tag_ids": [(6, 0, [cls.tag.id])],
            "stage_id": cls.stage.id,
            "pricelist_id": cls.pricelist1.id,
            "fiscal_position_id": cls.fiscal.id,
        }
        default_vals.update(vals)
        rec = cls.env["sale.subscription"].create(default_vals)
        return rec

    @classmethod
    def create_sub_line(cls, sub, prod=None):
        ssl = cls.env["sale.subscription.line"].create(
            {
                "company_id": 1,
                "sale_subscription_id": sub.id,
                "product_id": prod or cls.product_1.id,
            }
        )
        return ssl

    @classmethod
    def _create_price_list(cls, name):
        return cls.env["product.pricelist"].create(
            {
                "name": name,
                "active": True,
                "currency_id": cls.env.ref("base.USD").id,
                "company_id": cls.env.user.company_id.id,
            }
        )
