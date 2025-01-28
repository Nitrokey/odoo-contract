{
    "name": "Recurring Payment with Stripe",
    "version": "15.0.1.0.0",
    "summary": """Recurring Payment with Stripe""",
    "author": "Binhex, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "license": "AGPL-3",
    "category": "Subscription Management",
    "depends": ["subscription_recurring_payment", "payment_stripe"],
    "data": [
        "data/ir_cron.xml",
    ],
    "installable": True,
    "auto_install": False,
    "external_dependencies": {"python": ["stripe"]},
    "maintainers": ["mjavint"],
}
