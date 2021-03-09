# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.osv import expression


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    is_overdue = fields.Boolean('Is overdue', compute="_compute_is_overdue",
        help="Indicates more support time has been delivered thant the ordered quantity")
    use_helpdesk_sale_timesheet = fields.Boolean('Reinvoicing Timesheet activated on Team', related='team_id.use_helpdesk_sale_timesheet', readonly=True)

    @api.depends('task_id.sale_line_id')
    def _compute_is_overdue(self):
        self.is_overdue = False
        for ticket in self.filtered('task_id.sale_line_id'):
            sale_line_id = ticket.task_id.sale_line_id
            ticket.is_overdue = sale_line_id.qty_delivered >= sale_line_id.product_uom_qty

    @api.onchange('partner_id', 'project_id')
    def _onchange_partner_project(self):
        result = {}
        if self.project_id and self.use_helpdesk_sale_timesheet:
            domain = [('project_id', '=', self.project_id.id)]
            if self.partner_id:
                domain = expression.AND([domain, [
                    '|',
                    ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
                    ('partner_id', '=', False),
                ]])
            result = {'domain': {'task_id': domain}}
        else:
            self.task_id = False
        return result


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.model
    def _timesheet_preprocess(self, values):
        values = super(AccountAnalyticLine, self)._timesheet_preprocess(values)
        # TODO JEM: clean this. Need to set the SOL when changing the task in order to always have the SOL in project map, or task'SOL or SOL of the project (python constraint)
        if 'task_id' in values and not values.get('so_line'):
            task = self.env['project.task'].sudo().browse(values['task_id'])
            if task.billable_type == 'task_rate':
                values['so_line'] = task.sale_line_id.id
        return values
