from odoo import fields, models


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    payment_token_id = fields.Many2one(
        string="Payment Token",
        comodel_name="payment.token",
    )
