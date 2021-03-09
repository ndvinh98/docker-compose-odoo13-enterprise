# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, time
from collections import defaultdict
from odoo import api, fields, models
from odoo.tools import date_utils

import pytz


class HrContract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    structure_type_id = fields.Many2one('hr.payroll.structure.type', string="Salary Structure Type")
    schedule_pay = fields.Selection(related='structure_type_id.default_struct_id.schedule_pay', depends=())
    resource_calendar_id = fields.Many2one(required=True, default=lambda self: self.env.company.resource_calendar_id,
        help="Employee's working schedule.")
    hours_per_week = fields.Float(related='resource_calendar_id.hours_per_week')
    full_time_required_hours = fields.Float(related='resource_calendar_id.full_time_required_hours')
    is_fulltime = fields.Boolean(related='resource_calendar_id.is_fulltime')
    wage_type = fields.Selection([('monthly', 'Monthly Fixed Wage'), ('hourly', 'Hourly Wage')], related='structure_type_id.wage_type')
    hourly_wage = fields.Monetary('Hourly Wage', digits=(16, 2), default=0, required=True, tracking=True, help="Employee's hourly gross wage.")

    date_generated_from = fields.Datetime(string='Generated From', readonly=True, required=True,
        default=lambda self: datetime.now().replace(hour=0, minute=0, second=0), copy=False)
    date_generated_to = fields.Datetime(string='Generated To', readonly=True, required=True,
        default=lambda self: datetime.now().replace(hour=0, minute=0, second=0), copy=False)

    company_country_id = fields.Many2one('res.country', string="Company country", related='company_id.country_id', readonly=True)

    @api.constrains('date_start', 'date_end', 'state')
    def _check_contracts(self):
        self._get_leaves()._check_contracts()

    @api.onchange('structure_type_id')
    def _onchange_structure_type_id(self):
        if self.structure_type_id.default_resource_calendar_id:
            self.resource_calendar_id = self.structure_type_id.default_resource_calendar_id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            structure_types = self.env['hr.payroll.structure.type'].search([
                '|',
                ('country_id', '=', self.company_id.country_id.id),
                ('country_id', '=', False)])
            if structure_types:
                self.structure_type_id = structure_types[0]
            elif self.structure_type_id not in structure_types:
                self.structure_type_id = False

    def _get_leaves(self):
        return self.env['hr.leave'].search([
            ('employee_id', 'in', self.mapped('employee_id.id')),
            ('date_from', '<=', max([end or date.max for end in self.mapped('date_end')])),
            ('date_to', '>=', min(self.mapped('date_start'))),
        ])

    def _get_work_entries_values(self, date_start, date_stop):
        """
        Generate a work_entries list between date_start and date_stop for one contract.
        :return: list of dictionnary.
        """
        default_work_entry_type = self.structure_type_id.default_work_entry_type_id
        vals_list = []

        for contract in self:
            contract_vals = []
            employee = contract.employee_id
            calendar = contract.resource_calendar_id
            resource = employee.resource_id
            tz = pytz.timezone(calendar.tz)

            attendances = calendar._work_intervals_batch(
                pytz.utc.localize(date_start) if not date_start.tzinfo else date_start,
                pytz.utc.localize(date_stop) if not date_stop.tzinfo else date_stop,
                resources=resource, tz=tz
            )[resource.id]
            # Attendances
            for interval in attendances:
                work_entry_type_id = interval[2].mapped('work_entry_type_id')[:1] or default_work_entry_type
                # All benefits generated here are using datetimes converted from the employee's timezone
                contract_vals += [{
                    'name': "%s: %s" % (work_entry_type_id.name, employee.name),
                    'date_start': interval[0].astimezone(pytz.utc).replace(tzinfo=None),
                    'date_stop': interval[1].astimezone(pytz.utc).replace(tzinfo=None),
                    'work_entry_type_id': work_entry_type_id.id,
                    'employee_id': employee.id,
                    'contract_id': contract.id,
                    'company_id': contract.company_id.id,
                    'state': 'draft',
                }]

            # Leaves
            leaves = self.env['resource.calendar.leaves'].sudo().search([
                ('resource_id', 'in', [False, resource.id]),
                ('calendar_id', '=', calendar.id),
                ('date_from', '<', date_stop),
                ('date_to', '>', date_start)
            ])

            for leave in leaves:
                start = max(leave.date_from, datetime.combine(contract.date_start, datetime.min.time()))
                end = min(leave.date_to, datetime.combine(contract.date_end or date.max, datetime.max.time()))
                if leave.holiday_id:
                    work_entry_type = leave.holiday_id.holiday_status_id.work_entry_type_id
                else:
                    work_entry_type = leave.mapped('work_entry_type_id')
                contract_vals += [{
                    'name': "%s%s" % (work_entry_type.name + ": " if work_entry_type else "", employee.name),
                    'date_start': start,
                    'date_stop': end,
                    'work_entry_type_id': work_entry_type.id,
                    'employee_id': employee.id,
                    'leave_id': leave.holiday_id and leave.holiday_id.id,
                    'company_id': contract.company_id.id,
                    'state': 'draft',
                    'contract_id': contract.id,
                }]

            # If we generate work_entries which exceeds date_start or date_stop, we change boundaries on contract
            if contract_vals:
                date_stop_max = max([x['date_stop'] for x in contract_vals])
                if date_stop_max > contract.date_generated_to:
                    contract.date_generated_to = date_stop_max

                date_start_min = min([x['date_start'] for x in contract_vals])
                if date_start_min < contract.date_generated_from:
                    contract.date_generated_from = date_start_min

            vals_list += contract_vals

        return vals_list

    def _generate_work_entries(self, date_start, date_stop):
        vals_list = []

        date_start = fields.Datetime.to_datetime(date_start)
        date_stop = datetime.combine(fields.Datetime.to_datetime(date_stop), datetime.max.time())

        for contract in self:
            # For each contract, we found each interval we must generate
            contract_start = fields.Datetime.to_datetime(contract.date_start)
            contract_stop = datetime.combine(fields.Datetime.to_datetime(contract.date_end or datetime.max.date()), datetime.max.time())
            last_generated_from = min(contract.date_generated_from, contract_stop)
            date_start_work_entries = max(date_start, contract_start)

            if last_generated_from > date_start_work_entries:
                contract.date_generated_from = date_start_work_entries
                vals_list.extend(contract._get_work_entries_values(date_start_work_entries, last_generated_from))

            last_generated_to = max(contract.date_generated_to, contract_start)
            date_stop_work_entries = min(date_stop, contract_stop)
            if last_generated_to < date_stop_work_entries:
                contract.date_generated_to = date_stop_work_entries
                vals_list.extend(contract._get_work_entries_values(last_generated_to, date_stop_work_entries))

        if not vals_list:
            return self.env['hr.work.entry']

        return self.env['hr.work.entry'].create(vals_list)

    def _index_contracts(self):
        action = self.env.ref('hr_payroll.action_hr_payroll_index').read()[0]
        action['context'] = repr(self.env.context)
        return action

    def _get_work_hours(self, date_from, date_to):
        """
        Returns the amount (expressed in hours) of work
        for a contract between two dates.
        If called on multiple contracts, sum work amounts of each contract.
        :param date_from: The start date
        :param date_to: The end date
        :returns: a dictionary {work_entry_id: hours_1, work_entry_2: hours_2}
        """

        generated_date_max = min(fields.Date.to_date(date_to), date_utils.end_of(fields.Date.today(), 'month'))
        self._generate_work_entries(date_from, generated_date_max)
        date_from = datetime.combine(date_from, datetime.min.time())
        date_to = datetime.combine(date_to, datetime.max.time())
        work_data = defaultdict(int)

        # First, found work entry that didn't exceed interval.
        work_entries = self.env['hr.work.entry'].read_group(
            [
                ('state', 'in', ['validated', 'draft']),
                ('date_start', '>=', date_from),
                ('date_stop', '<=', date_to),
                ('contract_id', 'in', self.ids),
            ],
            ['hours:sum(duration)'],
            ['work_entry_type_id']
        )
        work_data.update({data['work_entry_type_id'][0] if data['work_entry_type_id'] else False: data['hours'] for data in work_entries})

        # Second, found work entry that exceed interval and compute right duration.
        work_entries = self.env['hr.work.entry'].search(
            [
                '&', '&',
                ('state', 'in', ['validated', 'draft']),
                ('contract_id', 'in', self.ids),
                '|', '|', '&', '&',
                ('date_start', '>=', date_from),
                ('date_start', '<', date_to),
                ('date_stop', '>', date_to),
                '&', '&',
                ('date_start', '<', date_from),
                ('date_stop', '<=', date_to),
                ('date_stop', '>', date_from),
                '&',
                ('date_start', '<', date_from),
                ('date_stop', '>', date_to),
            ]
        )

        for work_entry in work_entries:
            date_start = max(date_from, work_entry.date_start)
            date_stop = min(date_to, work_entry.date_stop)
            if work_entry.work_entry_type_id.is_leave:
                contract = work_entry.contract_id
                calendar = contract.resource_calendar_id
                employee = contract.employee_id
                contract_data = employee._get_work_days_data_batch(
                    date_start, date_stop, compute_leaves=False, calendar=calendar
                )[employee.id]

                work_data[work_entry.work_entry_type_id.id] += contract_data.get('hours', 0)
            else:
                dt = date_stop - date_start
                work_data[work_entry.work_entry_type_id.id] += dt.days * 24 + dt.seconds / 3600  # Number of hours
        return work_data

    def _remove_work_entries(self):
        ''' Remove all work_entries that are outside contract period (function used after writing new start or/and end date) '''
        all_we_to_unlink = self.env['hr.work.entry']
        for contract in self:
            date_start = fields.Datetime.to_datetime(contract.date_start)
            if contract.date_generated_from < date_start:
                we_to_remove = self.env['hr.work.entry'].search([('date_stop', '<=', date_start), ('contract_id', '=', contract.id)])
                if we_to_remove:
                    contract.date_generated_from = date_start
                    all_we_to_unlink |= we_to_remove
            if not contract.date_end:
                continue
            date_end = datetime.combine(contract.date_end, datetime.max.time())
            if contract.date_generated_to > date_end:
                we_to_remove = self.env['hr.work.entry'].search([('date_start', '>=', date_end), ('contract_id', '=', contract.id)])
                if we_to_remove:
                    contract.date_generated_to = date_end
                    all_we_to_unlink |= we_to_remove
        all_we_to_unlink.unlink()

    def write(self, vals):
        result = super(HrContract, self).write(vals)
        if vals.get('date_end') or vals.get('date_start'):
            self._remove_work_entries()
        return result
