# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time

from odoo import api, fields, models
from odoo.tools import float_round


class Employee(models.Model):
    _inherit = 'hr.employee'

    def _get_timesheet_manager_id_domain(self):
        group = self.env.ref('hr_timesheet.group_hr_timesheet_approver', raise_if_not_found=False)
        return [('groups_id', 'in', [group.id])] if group else []

    timesheet_validated = fields.Date(
        "Timesheets Validation Date", groups="hr.group_hr_user",
        help="Date until which the employee's timesheets have been validated")
    timesheet_manager_id = fields.Many2one(
        'res.users', string='Timesheet',
        domain=_get_timesheet_manager_id_domain,
        help="User responsible of timesheet validation. Should be Timesheet Manager.")

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        super(Employee, self)._onchange_parent_id()
        previous_manager = self._origin.parent_id.user_id
        manager = self.parent_id.user_id
        if manager and manager.has_group('hr_timesheet.group_timesheet_manager') and (self.timesheet_manager_id == previous_manager or not self.timesheet_manager_id):
            self.timesheet_manager_id = manager

    def get_timesheet_and_working_hours(self, date_start, date_stop):
        """ Get the difference between the supposed working hour (based on resource calendar) and
            the timesheeted hours, for the given period `date_start` - `date_stop` (inclusives).
            :param date_start : start date of the period to check (date string)
            :param date_stop : end date of the period to check (date string)
            :returns dict : a dict mapping the employee_id with his timesheeted and working hours for the
                given period.
        """
        employees = self.filtered(lambda emp: emp.resource_calendar_id)
        result = {i: dict(timesheet_hours=0.0, working_hours=0.0, date_start=date_start, date_stop=date_stop) for i in self.ids}
        if not employees:
            return result

        # find timesheeted hours of employees with working hours
        self.env.cr.execute("""
            SELECT A.employee_id as employee_id, sum(A.unit_amount) as amount_sum
            FROM account_analytic_line A
            WHERE A.employee_id IN %s AND date >= %s AND date <= %s
            GROUP BY A.employee_id
        """, (tuple(employees.ids), date_start, date_stop))
        for data_row in self.env.cr.dictfetchall():
            result[data_row['employee_id']]['timesheet_hours'] = float_round(data_row['amount_sum'], 2)

        # find working hours for the given period of employees with working calendar
        # Note: convert date str into datetime object. Time will be 00:00:00 and 23:59:59
        # respectively for date_start and date_stop, because we want the date_stop to be included.
        datetime_min = datetime.combine(fields.Date.from_string(date_start), time.min)
        datetime_max = datetime.combine(fields.Date.from_string(date_stop), time.max)

        employees_work_days_data = employees._get_work_days_data_batch(datetime_min, datetime_max, compute_leaves=False)
        for employee in employees:
            working_hours = employees_work_days_data[employee.id]['hours']
            result[employee.id]['working_hours'] = float_round(working_hours, 2)
        return result


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    timesheet_manager_id = fields.Many2one('res.users', string='Timesheet',
        help="User responsible of timesheet validation. Should be Timesheet Manager.")
