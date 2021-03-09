# -*- coding: utf-8 -*-
from odoo import models, fields


class product_template(models.Model):
    _inherit = "product.template"

    recurring_invoice = fields.Boolean('Subscription Product', help='If set, confirming a sale order with this product will create a subscription')
    subscription_template_id = fields.Many2one('sale.subscription.template', 'Subscription Template',
        help="Product will be included in a selected template")
