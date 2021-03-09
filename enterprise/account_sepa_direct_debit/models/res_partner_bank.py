# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    def unlink(self):
        if self.env['sdd.mandate'].search([('partner_bank_id', 'in', self.ids),('state','=','active')]):
            raise UserError(_('You cannot delete a bank account linked to an active SEPA Direct Debit mandate.'))
        return super(ResPartnerBank, self).unlink()