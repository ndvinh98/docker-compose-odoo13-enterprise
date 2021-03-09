# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import fields, models, _

class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    refund_in_payslip = fields.Boolean(
        string="Reimburse In Next Payslip", states={'done': [('readonly', True)], 'post': [('readonly', True)]},
        groups='hr_expense.group_hr_expense_team_approver,account.group_account_manager')
    payslip_id = fields.Many2one('hr.payslip', string="Payslip", readonly=True)

    def action_report_in_next_payslip(self):
        self.write({'refund_in_payslip': True})
        for record in self:
            record.message_post(
                body=_("Your expense (%s) will be added to your next payslip.") % (record.name),
                partner_ids=record.employee_id.user_id.partner_id.ids,
                subtype_id=self.env.ref('mail.mt_note').id,
                email_layout_xmlid='mail.mail_notification_light')

    def reset_expense_sheets(self):
        res = super().reset_expense_sheets()
        self.sudo().write({'refund_in_payslip': False})
        return res
