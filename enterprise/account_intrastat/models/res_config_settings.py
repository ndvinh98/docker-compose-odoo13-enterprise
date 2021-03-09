# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_country_id = fields.Many2one('res.country', string="Company country", readonly=True,
        related='company_id.country_id')
    incoterm_id = fields.Many2one('account.incoterms', string="Default incoterm for Intrastat", related='company_id.incoterm_id', readonly=False,
        help="International Commercial Terms are a series of predefined commercial terms used in international transactions.")
