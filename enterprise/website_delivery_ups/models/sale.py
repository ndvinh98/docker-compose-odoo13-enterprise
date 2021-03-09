# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_delivery_line(self, carrier, price_unit):
        if self.carrier_id.delivery_type == 'ups' and self.ups_bill_my_account and self.ups_carrier_account:
            return True
        return super(SaleOrder, self)._create_delivery_line(carrier, price_unit)

    @api.model
    def check_ups_service_type(self, value):
        if value.get('sale_id'):
            order = self.browse(int(value['sale_id']))
            order.ups_service_type = value.get('ups_service_type')
            check = order.carrier_id.ups_rate_shipment(order)
            if check['success']:
                return {}
            else:
                order.ups_service_type = order.carrier_id.ups_default_service_type
                return {'error': check['error_message']}
