# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.fields import Date, Datetime
from odoo.tests.common import TransactionCase


class TestPayslipBase(TransactionCase):

    def setUp(self):
        super(TestPayslipBase, self).setUp()

        # Some salary rules references
        self.hra_rule_id = self.ref('hr_payroll.hr_salary_rule_houserentallowance1')
        self.conv_rule_id = self.ref('hr_payroll.hr_salary_rule_convanceallowance1')
        self.prof_tax_rule_id = self.ref('hr_payroll.hr_salary_rule_professionaltax1')
        self.pf_rule_id = self.ref('hr_payroll.hr_salary_rule_providentfund1')
        self.mv_rule_id = self.ref('hr_payroll.hr_salary_rule_meal_voucher')
        self.sum_of_alw_id = self.ref('hr_payroll.hr_salary_rule_sum_alw_category')

        # I create a new employee "Richard"
        self.richard_emp = self.env['hr.employee'].create({
            'name': 'Richard',
            'gender': 'male',
            'birthday': '1984-05-01',
            'country_id': self.ref('base.be'),
            'department_id': self.ref('hr.dep_rd')
        })

        # I create a new employee "Jules"
        self.jules_emp = self.env['hr.employee'].create({
            'name': 'Jules',
            'gender': 'male',
            'birthday': '1984-05-01',
            'country_id': self.ref('base.be'),
            'department_id': self.ref('hr.dep_rd')
        })

        self.structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer',
        })

        # I create a contract for "Richard"
        self.env['hr.contract'].create({
            'date_end': Date.today() + relativedelta(years=2),
            'date_start': Date.to_date('2018-01-01'),
            'name': 'Contract for Richard',
            'wage': 5000.0,
            'employee_id': self.richard_emp.id,
            'structure_type_id': self.structure_type.id,
        })

        self.work_entry_type = self.env['hr.work.entry.type'].create({
            'name': 'Extra attendance',
            'is_leave': False,
            'code': 'WORKTEST200',
        })

        self.work_entry_type_unpaid = self.env['hr.work.entry.type'].create({
            'name': 'Unpaid Leave',
            'is_leave': True,
            'code': 'LEAVETEST300',
            'round_days': 'HALF',
            'round_days_type': 'DOWN',
        })
        self.leave_type_unpaid = self.env['hr.leave.type'].create({
            'name': 'Unpaid Leaves',
            'time_type': 'leave',
            'allocation_type': 'no',
            'validity_start': False,
            'work_entry_type_id': self.work_entry_type_unpaid.id
        })

        self.work_entry_type_leave = self.env['hr.work.entry.type'].create({
            'name': 'Leave',
            'is_leave': True,
            'code': 'LEAVETEST100'
        })
        self.leave_type = self.env['hr.leave.type'].create({
            'name': 'Legal Leaves',
            'time_type': 'leave',
            'allocation_type': 'no',
            'validity_start': False,
            'work_entry_type_id': self.work_entry_type_leave.id
        })

        # I create a salary structure for "Software Developer"
        self.developer_pay_structure = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Software Developer',
            'type_id': self.structure_type.id,
            'regular_pay': True,
            'rule_ids': [
                (4, self.hra_rule_id), (4, self.conv_rule_id),
                (4, self.prof_tax_rule_id), (4, self.pf_rule_id),
                (4, self.mv_rule_id), (4, self.sum_of_alw_id),
            ],
            'unpaid_work_entry_type_ids': [(4, self.work_entry_type_unpaid.id, False)]
        })

    def create_work_entry(self, start, stop, work_entry_type=None):
        work_entry_type = work_entry_type or self.work_entry_type
        return self.env['hr.work.entry'].create({
            'contract_id': self.richard_emp.contract_ids[0].id,
            'name': "Work entry %s-%s" % (start, stop),
            'date_start': start,
            'date_stop': stop,
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': work_entry_type.id,
        })

    def create_leave(self, date_from=None, date_to=None):
        date_from = date_from or Datetime.today()
        date_to = date_to or Datetime.today() + relativedelta(days=1)
        return self.env['hr.leave'].create({
            'name': 'Holiday !!!',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type.id,
            'date_to': date_to,
            'date_from': date_from,
            'number_of_days': 1,
        })


class TestPayslipContractBase(TestPayslipBase):

    def setUp(self):
        super(TestPayslipContractBase, self).setUp()
        self.calendar_richard = self.env['resource.calendar'].create({'name': 'Calendar of Richard'})
        self.calendar_40h = self.env['resource.calendar'].create({'name': 'Default calendar'})
        self.calendar_35h = self.env['resource.calendar'].create({
            'name': '35h calendar',
            'attendance_ids': [
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Evening', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Evening', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Evening', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Evening', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Friday Evening', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'})
            ]
        })
        self.calendar_35h._onchange_hours_per_day() # update hours/day

        self.calendar_2_weeks = self.env['resource.calendar'].create({
            'name': 'Week 1: 30 Hours - Week 2: 16 Hours',
            'two_weeks_calendar': True,
            'attendance_ids': [
                (0, 0, {'name': 'Monday', 'sequence': '1', 'week_type': '0', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Monday', 'sequence': '26', 'week_type': '1', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Tuesday', 'sequence': '2', 'week_type': '0', 'dayofweek': '1', 'hour_from': 9, 'hour_to': 17}),
                (0, 0, {'name': 'Wednesday', 'sequence': '27', 'week_type': '1', 'dayofweek': '2', 'hour_from': 7, 'hour_to': 15}),
                (0, 0, {'name': 'Thursday', 'sequence': '28', 'week_type': '1', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Friday', 'sequence': '29', 'week_type': '1', 'dayofweek': '4', 'hour_from': 10, 'hour_to': 18}),
                (0, 0, {'name': 'Even week', 'dayofweek': '0', 'sequence': '0', 'hour_from': 0, 'day_period': 'morning', 'week_type': '0', 'hour_to': 0, 'display_type': 'line_section'}),
                (0, 0, {'name': 'Odd week', 'dayofweek': '0', 'sequence': '25', 'hour_from': 0, 'day_period': 'morning', 'week_type': '1', 'hour_to': 0, 'display_type': 'line_section'}),
            ]
        })
        self.calendar_2_weeks._onchange_hours_per_day() # update hours/day

        self.richard_emp.resource_calendar_id = self.calendar_richard
        self.jules_emp.resource_calendar_id = self.calendar_2_weeks

        self.calendar_16h = self.env['resource.calendar'].create({
            'name': '16h calendar',
            'attendance_ids': [
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 11.5, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 11.5, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 11.5, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 9, 'hour_to': 12.5, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Evening', 'dayofweek': '3', 'hour_from': 13.5, 'hour_to': 15.5, 'day_period': 'afternoon'}),
            ]
        })
        self.calendar_16h._onchange_hours_per_day() # update hours/day

        self.calendar_38h_friday_light = self.env['resource.calendar'].create({
            'name': '38 calendar Friday light',
            'attendance_ids': [
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Evening', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17.5, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Evening', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17.5, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Evening', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17.5, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Evening', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 17.5, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
            ]
        })
        self.calendar_38h_friday_light._onchange_hours_per_day() # update hours/day

        # This contract ends at the 15th of the month
        self.contract_cdd = self.env['hr.contract'].create({ # Fixed term contract
            'date_end': datetime.strptime('2015-11-15', '%Y-%m-%d'),
            'date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'name': 'First CDD Contract for Richard',
            'resource_calendar_id': self.calendar_40h.id,
            'wage': 5000.0,
            'employee_id': self.richard_emp.id,
            'structure_type_id': self.structure_type.id,
            'state': 'open',
            'kanban_state': 'blocked',
            'date_generated_from': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'date_generated_to': datetime.strptime('2015-11-16', '%Y-%m-%d'),
        })

        # This contract starts the next day
        self.contract_cdi = self.env['hr.contract'].create({
            'date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'name': 'Contract for Richard',
            'resource_calendar_id': self.calendar_35h.id,
            'wage': 5000.0,
            'employee_id': self.richard_emp.id,
            'structure_type_id': self.structure_type.id,
            'state': 'open',
            'kanban_state': 'normal',
            'date_generated_from': datetime.strptime('2015-11-15', '%Y-%m-%d'),
            'date_generated_to': datetime.strptime('2015-11-15', '%Y-%m-%d'),
        })

        # Contract for Jules
        self.contract_jules = self.env['hr.contract'].create({
            'date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'name': 'Contract for Jules',
            'resource_calendar_id': self.calendar_2_weeks.id,
            'wage': 5000.0,
            'employee_id': self.jules_emp.id,
            'structure_type_id': self.developer_pay_structure.type_id.id,
            'state': 'open',
        })
