# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pytz

from collections import defaultdict
from contextlib import contextmanager
from itertools import chain
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.hr_payroll.models.hr_work_intervals import WorkIntervals


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    contract_id = fields.Many2one('hr.contract', string="Contract", required=True)
    leave_id = fields.Many2one('hr.leave', string='Time Off')
    leave_state = fields.Selection(related='leave_id.state')
    employee_id = fields.Many2one(domain=[('contract_ids.state', 'in', ('open', 'pending'))])

    @api.onchange('employee_id', 'date_start', 'date_stop')
    def _onchange_contract_id(self):
        vals = {
            'employee_id': self.employee_id.id,
            'date_start': self.date_start,
            'date_stop': self.date_stop,
        }
        try:
            res = self._set_current_contract(vals)
        except ValidationError:
            return
        if res.get('contract_id'):
            self.contract_id = res.get('contract_id')

    @api.depends('work_entry_type_id', 'leave_id', 'contract_id')
    def _compute_duration(self):
        super(HrWorkEntry, self)._compute_duration()

    def _inverse_duration(self):
        for work_entry in self:
            if work_entry.work_entry_type_id.is_leave or work_entry.leave_id:
                calendar = work_entry.contract_id.resource_calendar_id
                if not calendar:
                    continue
                work_entry.date_stop = calendar.plan_hours(self.duration, self.date_start, compute_leaves=True)
                continue
            super(HrWorkEntry, work_entry)._inverse_duration()

    def _get_duration(self, date_start, date_stop):
        if not date_start or not date_stop:
            return 0
        if self.work_entry_type_id and self.work_entry_type_id.is_leave or self.leave_id:
            calendar = self.contract_id.resource_calendar_id
            if not calendar:
                return 0
            employee = self.contract_id.employee_id
            contract_data = employee._get_work_days_data_batch(
                date_start, date_stop, compute_leaves=False, calendar=calendar)[employee.id]
            return contract_data.get('hours', 0)
        return super()._get_duration(date_start, date_stop)

    def write(self, vals):
        if 'state' in vals and vals['state'] == 'cancelled':
            self.mapped('leave_id').filtered(lambda l: l.state != 'refuse').action_refuse()
        return super().write(vals)

    @api.model
    def _set_current_contract(self, vals):
        if not vals.get('contract_id') and vals.get('date_start') and vals.get('date_stop') and vals.get('employee_id'):
            contract_start = fields.Datetime.to_datetime(vals.get('date_start')).date()
            contract_end = fields.Datetime.to_datetime(vals.get('date_stop')).date()
            employee = self.env['hr.employee'].browse(vals.get('employee_id'))
            contracts = employee._get_contracts(contract_start, contract_end, states=['open', 'pending', 'close'])
            if not contracts:
                raise ValidationError(_("%s does not have a contract from %s to %s.") % (employee.name, contract_start, contract_end))
            elif len(contracts) > 1:
                raise ValidationError(_("%s has multiple contracts from %s to %s. A work entry cannot overlap multiple contracts.")
                                      % (employee.name, contract_start, contract_end))
            return dict(vals, contract_id=contracts[0].id)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._set_current_contract(vals) for vals in vals_list]
        work_entries = super().create(vals_list)
        return work_entries

    def _reset_conflicting_state(self):
        super()._reset_conflicting_state()
        attendances = self.filtered(lambda w: not w.work_entry_type_id.is_leave)
        attendances.write({'leave_id': False})

    def _check_if_error(self):
        res = super()._check_if_error()
        conflict_with_leaves = self._compute_conflicts_leaves_to_approve()
        outside_calendar = self._mark_leaves_outside_schedule()
        return res or conflict_with_leaves or outside_calendar

    def _mark_leaves_outside_schedule(self):
        """
        Check leave work entries in `self` which are completely outside
        the contract's theoretical calendar schedule. Mark them as conflicting.
        :return: leave work entries completely outside the contract's calendar
        """
        work_entries = self.filtered(lambda w: w.work_entry_type_id.is_leave and w.state not in ('validated', 'cancelled'))
        entries_by_calendar = defaultdict(lambda: self.env['hr.work.entry'])
        for work_entry in work_entries:
            calendar = work_entry.contract_id.resource_calendar_id
            entries_by_calendar[calendar] |= work_entry

        outside_entries = self.env['hr.work.entry']
        for calendar, entries in entries_by_calendar.items():
            datetime_start = min(entries.mapped('date_start'))
            datetime_stop = max(entries.mapped('date_stop'))

            calendar_intervals = calendar._attendance_intervals_batch(pytz.utc.localize(datetime_start), pytz.utc.localize(datetime_stop))[False]
            entries_intervals = entries._to_intervals()
            overlapping_entries = self._from_intervals(entries_intervals & calendar_intervals)
            outside_entries |= entries - overlapping_entries
        outside_entries.write({'state': 'conflict'})
        return bool(outside_entries)

    def _compute_conflicts_leaves_to_approve(self):
        if not self:
            return False

        self.flush(['date_start', 'date_stop', 'employee_id'])
        self.env['hr.leave'].flush(['date_from', 'date_to', 'state', 'employee_id'])

        query = """
            SELECT
                b.id AS work_entry_id,
                l.id AS leave_id
            FROM hr_work_entry b
            INNER JOIN hr_leave l ON b.employee_id = l.employee_id
            WHERE
                b.active = TRUE AND
                b.id IN %s AND
                l.date_from < b.date_stop AND
                l.date_to > b.date_start AND
                l.state IN ('confirm', 'validate1');
        """
        self.env.cr.execute(query, [tuple(self.ids)])
        conflicts = self.env.cr.dictfetchall()
        for res in conflicts:
            self.browse(res.get('work_entry_id')).write({
                'state': 'conflict',
                'leave_id': res.get('leave_id')
            })
        return bool(conflicts)

    def action_approve_leave(self):
        self.ensure_one()
        if self.leave_id:
            # Already confirmed once
            if self.leave_id.state == 'validate1':
                self.leave_id.action_validate()
            # Still in confirmed state
            else:
                self.leave_id.action_approve()
                # If double validation, still have to validate it again
                if self.leave_id.validation_type == 'both':
                    self.leave_id.action_validate()

    def action_refuse_leave(self):
        self.ensure_one()
        if self.leave_id:
            self.leave_id.action_refuse()

    def _to_intervals(self):
        return WorkIntervals((w.date_start.replace(tzinfo=pytz.utc), w.date_stop.replace(tzinfo=pytz.utc), w) for w in self)

    @api.model
    def _from_intervals(self, intervals):
        return self.browse(chain.from_iterable(recs.ids for start, end, recs in intervals))


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'
    _description = 'HR Work Entry Type'

    _sql_constraints = [
        ('is_unforeseen_is_leave', 'check (is_unforeseen IS NOT TRUE OR (is_leave = TRUE and is_unforeseen = TRUE))', 'A unforeseen absence must be a leave.')
    ]

    is_unforeseen = fields.Boolean(default=False, string="Unforeseen Absence")
    round_days = fields.Selection([('NO', 'No Rounding'), ('HALF', 'Half Day'), ('FULL', 'Day')], string="Rounding", required=True, default='NO')
    round_days_type = fields.Selection([('HALF-UP', 'Closest'), ('UP', 'Up'), ('DOWN', 'Down')], string="Round Type", required=True, default='DOWN')
    leave_type_ids = fields.One2many('hr.leave.type', 'work_entry_type_id', string='Time Off Type')
    is_leave = fields.Boolean(default=False, string="Time Off")
