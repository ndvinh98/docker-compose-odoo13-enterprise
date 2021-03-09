# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    appraisal_date = fields.Date(string='Last Appraisal date', groups="hr.group_hr_user",
        help="The date of the next appraisal is computed by the appraisal plan's dates (last appraisal + periodicity).")
    appraisal_date_related = fields.Date(related="appraisal_date", groups="hr.group_hr_user", string="Last Appraisal Date", help="Used to configure the last appraisal date", readonly=False)
    appraisal_by_manager = fields.Boolean(string='Managers', groups="hr.group_hr_user", default=lambda self: self.env.user.company_id.appraisal_by_manager)
    appraisal_manager_ids = fields.Many2many('hr.employee', 'emp_appraisal_manager_rel', 'hr_appraisal_id', groups="hr.group_hr_user", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    appraisal_by_colleagues = fields.Boolean(string='Colleagues', groups="hr.group_hr_user", default=lambda self: self.env.user.company_id.appraisal_by_colleagues)
    appraisal_colleagues_ids = fields.Many2many('hr.employee', 'emp_appraisal_colleagues_rel', 'hr_appraisal_id', groups="hr.group_hr_user", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    appraisal_self = fields.Boolean(string='Employee', groups="hr.group_hr_user",
        default=lambda self: self.env.user.company_id.appraisal_by_employee)
    appraisal_employee = fields.Char(string='Name', compute='_compute_name', groups="hr.group_hr_user")
    appraisal_by_collaborators = fields.Boolean(string='Collaborators', groups="hr.group_hr_user",
        default=lambda self: self.env.user.company_id.appraisal_by_collaborators)
    appraisal_collaborators_ids = fields.Many2many('hr.employee', 'emp_appraisal_subordinates_rel', 'hr_appraisal_id', groups="hr.group_hr_user", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    #TODO remove the useless field in master
    periodic_appraisal_created = fields.Boolean(string='Periodic Appraisal has been created', groups="hr.group_hr_user", default=False)  # Flag for the cron
    appraisal_count = fields.Integer(compute='_compute_appraisal_count', string='Appraisals', groups="hr.group_hr_user")
    related_partner_id = fields.Many2one('res.partner', compute='_compute_related_partner', groups="hr.group_hr_user")
    parent_user_id = fields.Many2one(related='parent_id.user_id', string="Parent User", groups="hr.group_hr_user")
    last_duration_reminder_send = fields.Integer(string='Duration after last appraisal when we send last reminder mail',
        groups="hr.group_hr_user", default=0)

    def _compute_name(self):
        for employee in self:
            employee.appraisal_employee = employee.name
    def _compute_appraisal_count(self):
        appraisal = self.env['hr.appraisal'].read_group([('employee_id', 'in', self.ids)], ['employee_id'], ['employee_id'])
        result = dict((data['employee_id'][0], data['employee_id_count']) for data in appraisal)
        for employee in self:
            employee.appraisal_count = result.get(employee.id, 0)

    def _compute_related_partner(self):
        for rec in self:
            rec.related_partner_id = rec.user_id.partner_id

    @api.onchange('appraisal_by_manager')
    def onchange_appraisal_by_manager(self):
        if not self.appraisal_manager_ids:
            self._onchange_manager_appraisal()

    @api.onchange('parent_id')
    def _onchange_manager_appraisal(self):
        if self.appraisal_by_manager and self.parent_id:
            self.appraisal_manager_ids = [self.parent_id.id]
        else:
            self.appraisal_manager_ids = False

    @api.onchange('appraisal_by_colleagues')
    def onchange_appraisal_by_colleagues(self):
        if not self.appraisal_colleagues_ids:
            self.onchange_colleagues()

    @api.onchange('department_id', 'parent_id')
    def onchange_colleagues(self):
        if self.appraisal_by_colleagues and self.department_id and self.parent_id:
            self.appraisal_colleagues_ids = self.search([('department_id', '=', self.department_id.id), ('id', '!=', self._origin.id), ('parent_id', '=', self.parent_id.id)])
        else:
            self.appraisal_colleagues_ids = False

    @api.onchange('appraisal_by_collaborators')
    def onchange_appraisal_by_collaborators(self):
        if not self.appraisal_collaborators_ids:
            self.onchange_subordinates()

    @api.onchange('child_ids')
    def onchange_subordinates(self):
        if self.appraisal_by_collaborators:
            self.appraisal_collaborators_ids = self.child_ids
        else:
            self.appraisal_collaborators_ids = False

    def _get_employees_to_send_reminder_appraisal(self, months, reminder):
        company_id = reminder.company_id.id
        current_date = datetime.date.today()
        if reminder.event == 'last_appraisal':
            return self.search([
                ('appraisal_date', '>', current_date - relativedelta(months=months+1)),
                ('appraisal_date', '<', current_date - relativedelta(months=months)),
                ('last_duration_reminder_send', '<', months),
                ('company_id', '=', company_id),
            ])
        return self.search([
            ('create_date', '>', current_date - relativedelta(months=months+1)),
            ('create_date', '<', current_date - relativedelta(months=months)),
            ('appraisal_date', '=', False),
            ('last_duration_reminder_send', '<', months),
            ('company_id', '=', company_id),
        ])

    def _get_employees_to_appraise(self, months):
        days = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_create_in_advance_days', 8))
        current_date = datetime.date.today()
        return self.search([
            ('appraisal_date', '<=', current_date - relativedelta(months=months, days=-days)),
        ])

    def _new_employee_appraisal_date(self):  #fixes appraisal date issues in 12.3 and 13.0, 13.1, drop in master
        current_date = datetime.date.today()
        months = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_max_period'))

        employees = self.search([('appraisal_date', '=', False)])
        appraisal_by_employee = defaultdict(self.env['hr.appraisal'].browse)
        for app in self.env['hr.appraisal'].search([('employee_id', 'in', employees.ids), ('state', '!=', 'cancel')]):
            appraisal_by_employee[app.employee_id] |= app

        for employee in employees:
            if appraisal_by_employee[employee]:
                date = max(appraisal_by_employee[employee].mapped('date_close'))
            # hr_appraisal doesn't depend on hr_contract
            elif 'hr.contract' in self.env and employee.contract_ids:
                date = min(employee.contract_ids.mapped('date_start'))
            else:
                date = employee.create_date.date()

            if date + relativedelta(months=months) < current_date:
                date = current_date - relativedelta(months=months)
            employee.write({
                'appraisal_date': date,
            })

    @api.model
    def run_employee_appraisal(self):  # cronjob
        self._new_employee_appraisal_date()
        current_date = datetime.date.today()
        months = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_max_period'))
        days = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_create_in_advance_days', 8))
        # Set periodic_appraisal_created for the next appraisal if the date is passed:
        # Create perdiodic appraisal if appraisal date is in less than a week and the appraisal for this perdiod has not been created yet:
        employees_to_appraise = self._get_employees_to_appraise(months)
        appraisal_values = [{
            'company_id': employee.company_id.id,
            'employee_id': employee.id,
            'date_close': fields.Date.to_string(current_date + relativedelta(days=days)),
            'manager_appraisal': employee.appraisal_by_manager,
            'manager_ids': [(4, manager.id) for manager in employee.appraisal_manager_ids],
            'manager_body_html': employee.company_id.appraisal_by_manager_body_html,
            'colleagues_appraisal': employee.appraisal_by_colleagues,
            'colleagues_ids': [(4, colleagues.id) for colleagues in employee.appraisal_colleagues_ids],
            'colleagues_body_html': employee.company_id.appraisal_by_colleagues_body_html,
            'employee_appraisal': employee.appraisal_self,
            'employee_body_html': employee.company_id.appraisal_by_employee_body_html,
            'collaborators_appraisal': employee.appraisal_by_collaborators,
            'collaborators_ids': [(4, subordinates.id) for subordinates in employee.appraisal_collaborators_ids],
            'collaborators_body_html': employee.company_id.appraisal_by_collaborators_body_html,
        } for employee in employees_to_appraise]
        appraisals = self.env['hr.appraisal'].create(appraisal_values)
        self.env['hr.appraisal.reminder']._run_employee_appraisal_reminder()
        return appraisals

    def action_send_appraisal_request(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'request.appraisal',
            'target': 'new',
            'name': 'Appraisal Request',
            'context': self.env.context,
        }
