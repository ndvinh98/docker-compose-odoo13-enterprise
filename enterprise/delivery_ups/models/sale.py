# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_ups_service_types(self):
        return self.env['delivery.carrier']._get_ups_service_types()

    ups_carrier_account = fields.Char(string='Carrier Account', copy=False)
    ups_service_type = fields.Selection(_get_ups_service_types, string="UPS Service Type")
    ups_bill_my_account = fields.Boolean(related='carrier_id.ups_bill_my_account', readonly=True)

    @api.onchange('carrier_id')
    def _onchange_carrier_id(self):
        self.ups_service_type = self.carrier_id.ups_default_service_type
