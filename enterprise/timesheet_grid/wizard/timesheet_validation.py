# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ValidationWizard(models.TransientModel):
    _name = 'timesheet.validation'
    _description = 'Timesheet Validation'

    validation_date = fields.Date('Validate up to')
    validation_line_ids = fields.One2many('timesheet.validation.line', 'validation_id')

    def action_validate(self):
        domain = False
        if self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
            domain = [('timesheet_manager_id', '=', self.env.user.id)]
        if self.env.user.has_group('hr_timesheet.group_timesheet_manager'):
            domain = []

        self.validation_line_ids.filtered('validate').mapped('employee_id').sudo().filtered_domain(domain).write({'timesheet_validated': self.validation_date}) # sudo needed because timesheet approver may not have access on hr.employee
        return {'type': 'ir.actions.act_window_close'}


class ValidationWizardLine(models.TransientModel):
    _name = 'timesheet.validation.line'
    _description = 'Timesheet Validation Line'

    validation_id = fields.Many2one('timesheet.validation', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, ondelete='cascade')
    validate = fields.Boolean(
        default=True, help="Validate this employee's timesheet up to the chosen date")
