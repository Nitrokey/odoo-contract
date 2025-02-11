{
    "name": "Subscription Recurring Payment with Stripe",
    "version": "15.0.1.0.0",
    "summary": """Subscription Recurring Payment with Stripe""",
    "author": "Binhex, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "license": "AGPL-3",
    "category": "Subscription Management",
    "depends": ["subscription_recurring_payment", "payment_stripe"],
    "data": [
        "views/sale_subscription_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "auto_install": False,
    "maintainers": ["Binhex", "mjavint"],
}
