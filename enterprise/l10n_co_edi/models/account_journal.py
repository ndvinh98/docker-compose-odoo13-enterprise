# coding: utf-8
from odoo import api, fields, models, _


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_co_edi_dian_authorization_number = fields.Char(string=u'Resolución de Facturación')
    l10n_co_edi_dian_authorization_date = fields.Date(string=u'Fecha de Resolución')
