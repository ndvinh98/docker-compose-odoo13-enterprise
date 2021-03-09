# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super(AccountPayment, self)._get_method_codes_using_bank_account()
        res.append('aba_ct')
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super(AccountPayment, self)._get_method_codes_needing_bank_account()
        res.append('aba_ct')
        return res

    @api.constrains('payment_method_id', 'journal_id', 'currency_id')
    def _check_bank_account(self):
        for rec in self:
            if rec.payment_method_id == self.env.ref('l10n_au_aba.account_payment_method_aba_ct'):
                bank_acc = rec.journal_id.bank_account_id

                if rec.currency_id.name != 'AUD':
                    raise ValidationError(_('ABA payments must be defined in AUD.'))

                if bank_acc.acc_type != 'aba' or not bank_acc.aba_bsb:
                    raise ValidationError(_("Journal '%s' requires a proper ABA account. Please configure it first.") % rec.journal_id.name)

                if not rec.journal_id.aba_user_spec or not rec.journal_id.aba_fic or not rec.journal_id.aba_user_number:
                    raise ValidationError(_("Please fill in the ABA data of account %s (journal %s) before using it to generate ABA payments.")
                        % (bank_acc.acc_number, rec.journal_id.name))

    @api.constrains('payment_method_id', 'partner_bank_account_id')
    def _check_partner_bank_account(self):
        for rec in self:
            if rec.payment_method_id == self.env.ref('l10n_au_aba.account_payment_method_aba_ct'):
                if rec.partner_bank_account_id.acc_type != 'aba' or not rec.partner_bank_account_id.aba_bsb:
                    raise ValidationError(_("The partner requires a bank account with a valid BSB and account number. Please configure it first."))

    @api.onchange('destination_journal_id')
    def _onchange_destination_journal_id(self):
        if hasattr(super(AccountPayment, self), '_onchange_destination_journal_id'):
            super(AccountPayment, self)._onchange_destination_journal_id()
        if self.destination_journal_id:
            bank_account = self.destination_journal_id.bank_account_id
            self.partner_id = bank_account.company_id.partner_id
            self.partner_bank_account_id = bank_account
