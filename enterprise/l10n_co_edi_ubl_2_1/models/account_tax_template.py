# coding: utf-8
from odoo import fields, models


class AccountTaxTemplate(models.Model):
    _inherit = 'account.tax.template'

    l10n_co_edi_type = fields.Many2one('l10n_co_edi.tax.type', string='Tipo de Valor')
