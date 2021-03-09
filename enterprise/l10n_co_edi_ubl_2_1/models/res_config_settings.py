# coding: utf-8
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_co_edi_template_code = fields.Selection(string="Colombia Template Code", readonly=False, related="company_id.l10n_co_edi_template_code")
