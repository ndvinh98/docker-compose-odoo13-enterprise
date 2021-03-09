# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.rrule import rrule, DAILY

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayrollAllocPaidLeave(models.TransientModel):
    _name = 'hr.payroll.alloc.paid.leave'
    _description = 'Manage the Allocation of Paid Time Off'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id != self.env.ref('base.be'):
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    date_start = fields.Date('Start Period', required=True, default=lambda self: fields.Date.today().replace(month=1, day=1),
        help="Start date of the period to consider.")
    date_end = fields.Date('End Period', required=True, default=lambda self: fields.Date.today().replace(month=12, day=31),
        help="End date of the period to consider.")
    structure_type_id = fields.Many2one('hr.payroll.structure.type', string="Structure Type")

    alloc_employee_ids = fields.Many2many('hr.payroll.alloc.employee')

    holiday_status_id = fields.Many2one(
        "hr.leave.type", string="Time Off Type", required=True,
        domain=[('valid', '=', True), ('allocation_type', '!=', 'no')])

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.onchange('structure_type_id', 'date_start', 'date_end')
    def _onchange_struct_id(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_("You don't have the right to do this. Please contact your administrator!"))
        self.alloc_employee_ids = False
        if not self.date_start or not self.date_end or not self.company_id or self.date_start > self.date_end:
            return

        # To compute paid leave: 2 * number_of_days_paid / (number_of_days_during_this_period_with_a_6_days_calendar / number_months_during_this_period)
        business_day = len(list(rrule(DAILY, dtstart=self.date_start, until=self.date_end, byweekday=[0, 1, 2, 3, 4, 5])))
        months = (self.date_end.year - self.date_start.year) * 12 + self.date_end.month - self.date_start.month + (self.date_end.day - self.date_start.day + 1) / 31
        coefficient = 2 * months / business_day

        period_start = fields.Date.to_string(self.date_start)
        period_end = fields.Date.to_string(self.date_end)
        if self.structure_type_id:
            structure = "structure_type_id = %(structure)s AND"
        else:
            structure = ""

        query = """
            SELECT employee_id, sum(number_of_days) as worked_days, ROUND(%(coeff)s * sum(number_of_days)) as paid_time_off
            FROM (
                SELECT contract.employee_id as employee_id, we.duration / calendar.hours_per_day as number_of_days
                FROM
                    (SELECT id, employee_id, resource_calendar_id FROM hr_contract
                        WHERE
                            {where_structure}
                            employee_id IS NOT NULL
                            AND state IN ('open', 'pending', 'close')
                            AND date_start <= %(stop)s
                            AND (date_end IS NULL OR date_end >= %(start)s)
                            AND company_id IN %(company)s
                    ) contract
                LEFT JOIN (
                    SELECT * FROM hr_work_entry
                    WHERE
                        work_entry_type_id IN (SELECT id FROM hr_work_entry_type WHERE leave_right IS TRUE)
                        AND date_start <= %(stop)s
                        AND date_stop >= %(start)s
                        AND state = 'validated'
                    ) we ON (we.contract_id = contract.id)
                LEFT JOIN resource_calendar calendar ON (contract.resource_calendar_id = calendar.id)
            ) payslip
            GROUP BY employee_id
        """.format(where_structure=structure)

        self.env.cr.execute(query, {'coeff': coefficient, 'start': period_start, 'stop': period_end, 'structure': self.structure_type_id.id, 'company': tuple(self.env.companies.ids)})
        self.alloc_employee_ids = [(0, 0, vals) for vals in self.env.cr.dictfetchall()]

    def generate_allocation(self):
        allocation_values = []
        for alloc in self.alloc_employee_ids.filtered(lambda alloc: alloc.paid_time_off):
            allocation_values.append({
                'name': _('Paid Time Off Allocation'),
                'holiday_status_id': self.holiday_status_id.id,
                'employee_id': alloc.employee_id.id,
                'number_of_days': alloc.paid_time_off
            })
        allocations = self.env['hr.leave.allocation'].create(allocation_values)

        return {
            'name': 'Paid Time Off Allocation',
            'domain': [('id', 'in', allocations.ids)],
            'res_model': 'hr.leave.allocation',
            'view_id': False,
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
        }


class HrPayrollAllocEmployee(models.TransientModel):
    _name = 'hr.payroll.alloc.employee'
    _description = 'Manage the Allocation of Paid Time Off Employee'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    worked_days = fields.Integer("Worked Days", required=True)
    paid_time_off = fields.Integer("Paid Time Off", required=True)
