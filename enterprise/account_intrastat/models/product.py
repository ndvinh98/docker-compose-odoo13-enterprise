# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    intrastat_id = fields.Many2one('account.intrastat.code', string='Commodity Code', domain="[('type', '=', 'commodity')]")
    intrastat_origin_country_id = fields.Many2one('res.country', string='Country of Origin')

    def search_intrastat_code(self):
        self.ensure_one()
        return self.intrastat_id or self.categ_id.search_intrastat_code()


class ProductCategory(models.Model):
    _inherit = "product.category"

    intrastat_id = fields.Many2one('account.intrastat.code', string='Commodity Code', domain=[('type', '=', 'commodity')])

    def search_intrastat_code(self):
        self.ensure_one()
        return self.intrastat_id or (self.parent_id and self.parent_id.search_intrastat_code())
