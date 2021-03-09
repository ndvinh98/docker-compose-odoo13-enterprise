# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class AccountJournalDashboard(models.Model):
    _inherit = "account.journal"

    def get_journal_dashboard_datas(self):
        domain_aba_ct_to_send = [
            ('journal_id', '=', self.id),
            ('payment_method_id.code', '=', 'aba_ct'),
            ('state','=','posted')
        ]
        return dict(
            super(AccountJournalDashboard, self).get_journal_dashboard_datas(),
            num_aba_ct_to_send=len(self.env['account.payment'].search(domain_aba_ct_to_send))
        )

    def action_aba_ct_to_send(self):
        return {
            'name': _('ABA Credit Transfers to Send'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form,graph',
            'res_model': 'account.payment',
            'context': dict(
                self.env.context,
                search_default_aba_to_send=1,
                journal_id=self.id,
                default_journal_id=self.id,
                default_payment_type='outbound',
                default_payment_method_id=self.env.ref('l10n_au_aba.account_payment_method_aba_ct').id,
            ),
        }
