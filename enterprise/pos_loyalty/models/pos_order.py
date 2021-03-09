# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    loyalty_points = fields.Float(help='The amount of Loyalty points the customer won or lost with this order')

    @api.model
    def _order_fields(self, ui_order):
        fields = super(PosOrder, self)._order_fields(ui_order)
        fields['loyalty_points'] = ui_order.get('loyalty_points', 0)
        return fields

    @api.model
    def create_from_ui(self, orders, draft=False):
        order_ids = super(PosOrder, self).create_from_ui(orders, draft)
        for order in self.sudo().browse([o['id'] for o in order_ids]):
            if order.loyalty_points != 0 and order.partner_id:
                order.partner_id.loyalty_points += order.loyalty_points
        return order_ids
