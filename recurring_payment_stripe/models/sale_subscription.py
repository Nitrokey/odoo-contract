from odoo import fields, models


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    charge_automatically = fields.Boolean(default=True)
    provider_id = fields.Many2one(
        string="Provider",
        domain=[("code", "=", "stripe")],
        comodel_name="payment.provider",
    )
