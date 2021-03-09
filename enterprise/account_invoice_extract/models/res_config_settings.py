# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    extract_show_ocr_option_selection = fields.Selection(related='company_id.extract_show_ocr_option_selection',
        string='Processing Option', readonly=False)
    extract_single_line_per_tax = fields.Boolean(related='company_id.extract_single_line_per_tax', string='OCR Single Invoice Line Per Tax', readonly=False)
