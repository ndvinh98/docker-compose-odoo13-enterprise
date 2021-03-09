# coding: utf-8
from odoo import api, fields, models, _


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_co_edi_type = fields.Many2one('l10n_co_edi.tax.type', string='Tipo de Valor')
    l10n_co_edi_country_code = fields.Char(related="company_id.country_id.code")
