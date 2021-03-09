# coding: utf-8
from odoo import fields, models

TEMPLATE_CODE = [
    ('01', 'CGEN03'),
    ('02', 'CGEN04'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_co_edi_template_code = fields.Selection(TEMPLATE_CODE, string="Colombia Template Code")

    def _get_l10n_co_edi_template_code_description(self):
        return dict(TEMPLATE_CODE).get(self.l10n_co_edi_template_code)
