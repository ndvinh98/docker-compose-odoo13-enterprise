# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ups_carrier_account = fields.Char(related='sale_id.ups_carrier_account', string='Carrier Account', readonly=False)
    ups_service_type = fields.Selection(related='sale_id.ups_service_type', string="UPS Service Type", readonly=False)
