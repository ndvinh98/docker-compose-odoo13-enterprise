# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    loyalty_id = fields.Many2one('loyalty.program', string='Pos Loyalty Program', help='The loyalty program used by this point of sale.')

    @api.onchange('module_pos_loyalty')
    def _onchange_module_pos_loyalty(self):
        if self.module_pos_loyalty:
            self.loyalty_id = self.env['loyalty.program'].search([], limit=1)
        else:
            self.loyalty_id = False
