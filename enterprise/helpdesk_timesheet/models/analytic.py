# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', 'Helpdesk Ticket')

    @api.onchange('project_id')
    def onchange_project_id(self):
        result = super(AccountAnalyticLine, self).onchange_project_id()
        if self.helpdesk_ticket_id:
            self.task_id = self.helpdesk_ticket_id.task_id
        return result

    def _timesheet_preprocess(self, vals):
        helpdesk_ticket_id = vals.get('helpdesk_ticket_id')
        if helpdesk_ticket_id:
            ticket = self.env['helpdesk.ticket'].browse(helpdesk_ticket_id)
            if ticket.project_id:
                vals['project_id'] = ticket.project_id.id
            if ticket.task_id:
                vals['task_id'] = ticket.task_id.id
        vals = super(AccountAnalyticLine, self)._timesheet_preprocess(vals)
        return vals
