# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    intrastat_product_origin_country_id = fields.Many2one('res.country', string='Product Country')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = super()._onchange_product_id()
        for line in self:
            line.intrastat_product_origin_country_id = line.product_id.product_tmpl_id.intrastat_origin_country_id
        return res
