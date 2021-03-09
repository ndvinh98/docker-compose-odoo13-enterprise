# -*- coding: utf-8 -*-

from odoo import models, api, _

class account_journal(models.Model):
    _inherit = "account.journal"

    def get_journal_dashboard_datas(self):
        domain_sepa_ct_to_send = [
            ('journal_id', '=', self.id),
            ('payment_method_id.code', '=', 'sepa_ct'),
            ('state','=','posted')
        ]
        return dict(
            super(account_journal, self).get_journal_dashboard_datas(),
            num_sepa_ct_to_send=len(self.env['account.payment'].search(domain_sepa_ct_to_send))
        )

    def action_sepa_ct_to_send(self):
        return {
            'name': _('SEPA Credit Transfers to Send'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form,graph',
            'res_model': 'account.payment',
            'context': dict(
                self.env.context,
                search_default_sepa_to_send=1,
                journal_id=self.id,
                default_journal_id=self.id,
                default_payment_type='outbound',
                default_payment_method_id=self.env.ref('account_sepa.account_payment_method_sepa_ct').id,
            ),
        }
