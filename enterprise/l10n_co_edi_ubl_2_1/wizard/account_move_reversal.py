# coding: utf-8
from odoo import fields, models

from ..models.account_invoice import DESCRIPTION_CREDIT_CODE


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    l10n_co_edi_description_code_credit = fields.Selection(DESCRIPTION_CREDIT_CODE, string="Concepto", help="Colombian code for Credit Notes")

    def reverse_moves(self):
        action = super(AccountMoveReversal, self).reverse_moves()
        if action.get('res_id'):
            refund = self.env['account.move'].browse(action['res_id'])
            if refund:
                refund.l10n_co_edi_description_code_credit = self.l10n_co_edi_description_code_credit
                refund._onchange_type()
        return action
