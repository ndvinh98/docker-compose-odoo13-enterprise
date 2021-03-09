# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    _description = 'Employee'

    slip_ids = fields.One2many('hr.payslip', 'employee_id', string='Payslips', readonly=True)
    payslip_count = fields.Integer(compute='_compute_payslip_count', string='Payslip Count', groups="hr_payroll.group_hr_payroll_user")
    registration_number = fields.Char('Registration Number of the Employee', groups="hr.group_hr_user", copy=False)

    _sql_constraints = [
        ('unique_registration_number', 'UNIQUE(registration_number, company_id)', 'No duplication of registration numbers is allowed')
    ]

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)

    def generate_work_entries(self, date_start, date_stop):
        date_start = fields.Date.to_date(date_start)
        date_stop = fields.Date.to_date(date_stop)

        if self:
            current_contracts = self._get_contracts(date_start, date_stop, states=['open', 'close'])
        else:
            current_contracts = self._get_all_contracts(date_start, date_stop, states=['open', 'close'])

        return bool(current_contracts._generate_work_entries(date_start, date_stop))
