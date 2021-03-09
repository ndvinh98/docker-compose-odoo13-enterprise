# coding: utf-8

from odoo import fields, models


class City(models.Model):
    _inherit = 'res.city'

    l10n_mx_edi_code = fields.Char(
        'Code MX', help='Code to use in the CFDI with external trade complement. '
        'It is based on the SAT catalog.')
