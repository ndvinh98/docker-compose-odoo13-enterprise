# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from odoo import api, fields, models, _
from odoo.exceptions import Warning, UserError
from odoo.osv import expression
from datetime import datetime, timedelta


class FollowupLine(models.Model):
    _name = 'account_followup.followup.line'
    _description = 'Follow-up Criteria'
    _order = 'delay asc'

    name = fields.Char('Follow-Up Action', required=True, translate=True)
    delay = fields.Integer('Due Days', required=True,
                           help="The number of days after the due date of the invoice to wait before sending the reminder.  Could be negative if you want to send a polite alert beforehand.")
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    sms_description = fields.Char('SMS Text Message', translate=True, default=lambda s: _("Dear %(partner_name)s, it seems that some of your payments stay unpaid"))
    description = fields.Text('Printed Message', translate=True, default=lambda s: _("""
Dear %(partner_name)s,

Exception made if there was a mistake of ours, it seems that the following amount stays unpaid. Please, take appropriate measures in order to carry out this payment in the next 8 days.

Would your payment have been carried out after this mail was sent, please ignore this message. Do not hesitate to contact our accounting department.

Best Regards,
            """))
    send_email = fields.Boolean('Send an Email', help="When processing, it will send an email", default=True)
    print_letter = fields.Boolean('Print a Letter', help="When processing, it will print a PDF", default=True)
    send_sms = fields.Boolean('Send an SMS Message', help="When processing, it will send an sms text message", default=False)
    join_invoices = fields.Boolean('Join open Invoices')
    manual_action = fields.Boolean('Manual Action', help="When processing, it will set the manual action to be taken for that customer. ", default=False)
    manual_action_note = fields.Text('Action To Do', placeholder="e.g. Give a phone call, check with others , ...")
    manual_action_type_id = fields.Many2one('mail.activity.type', 'Manual Action Type', default=False)
    manual_action_responsible_id = fields.Many2one('res.users', 'Assign a Responsible', ondelete='set null')

    auto_execute = fields.Boolean()

    _sql_constraints = [('days_uniq', 'unique(company_id, delay)', 'Days of the follow-up levels must be different per company')]

    def copy_data(self, default=None):
        default = dict(default or {})
        if not default or 'delay' not in default:
            company_id = self.company_id.id
            if default and 'company_id' in default:
                company_id = default['company_id']
            higher_delay = self.search([('company_id', '=', company_id)], order='delay desc', limit=1)[:1].delay or 0
            default['delay'] = higher_delay + 15
        return super(FollowupLine, self).copy_data(default=default)

    @api.constrains('description')
    def _check_description(self):
        for line in self:
            if line.description:
                try:
                    line.description % {'partner_name': '', 'date': '', 'user_signature': '', 'company_name': '', 'amount_due': ''}
                except KeyError:
                    raise Warning(_('Your description is invalid, use the right legend or %% if you want to use the percent character.'))

    @api.constrains('sms_description')
    def _check_sms_description(self):
        for line in self:
            if line.sms_description:
                try:
                    line.sms_description % {'partner_name': '', 'date': '', 'user_signature': '', 'company_name': '', 'amount_due': ''}
                except KeyError:
                    raise Warning(_('Your sms description is invalid, use the right legend or %% if you want to use the percent character.'))

    @api.onchange('auto_execute')
    def _onchange_auto_execute(self):
        if self.auto_execute:
            self.manual_action = False
            self.print_letter = False

    def _get_next_date(self):
        self.ensure_one()
        next_followup = self.env['account_followup.followup.line'].search([('delay', '>', self.delay),
                                                                           ('company_id', '=', self.env.company.id)],
                                                                          order="delay asc", limit=1)
        if next_followup:
            delay = next_followup.delay - self.delay
        else:
            delay = 14
        return fields.Date.today() + timedelta(days=delay)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    followup_line_id = fields.Many2one('account_followup.followup.line', 'Follow-up Level', copy=False)
    followup_date = fields.Date('Latest Follow-up', index=True, copy=False)
