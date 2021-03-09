# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class AccountFollowupReport(models.AbstractModel):
    _inherit = "account.followup.report"

    def _get_line_info(self, followup_line):
        res = super(AccountFollowupReport , self)._get_line_info(followup_line)
        res.update(send_letter=followup_line.send_letter)
        return res

    def _execute_followup_partner(self, partner):
        if partner.followup_status == 'in_need_of_action':
            followup_line = partner.followup_level
            if followup_line.send_letter:
                letter = self.env['snailmail.letter'].create({
                    'state': 'pending',
                    'partner_id': partner.id,
                    'model': 'res.partner',
                    'res_id': partner.id,
                    'user_id': self.env.user.id,
                    'report_template': self.env.ref('account_followup.action_report_followup').id,
                    # we will only process partners that are linked to the user current company
                    # TO BE CHECKED
                    'company_id': self.env.company.id,
                })
                letter._snailmail_print()
        return super(AccountFollowupReport, self)._execute_followup_partner(partner)
