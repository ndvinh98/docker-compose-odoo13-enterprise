# # -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.rrule import rrule, DAILY
from datetime import datetime, date, timedelta

from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


class TestPayslipComputation(TestPayslipContractBase):

    def setUp(self):
        super(TestPayslipComputation, self).setUp()

        self.richard_payslip = self.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': self.richard_emp.id,
            'contract_id': self.contract_cdi.id,  # wage = 5000 => average/day (over 3months/13weeks): 230.77
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        self.richard_emp.resource_calendar_id = self.contract_cdi.resource_calendar_id

        self.richard_payslip_quarter = self.env['hr.payslip'].create({
            'name': 'Payslip of Richard Quarter',
            'employee_id': self.richard_emp.id,
            'contract_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 3, 31)
        })

    def test_work_data(self):
        leave = self.env['hr.leave'].create({
            'name': 'Doctor Appointment',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type.id,
            'date_from': datetime(2015, 11, 8, 8, 0),
            'date_to': datetime(2015, 11, 10, 22, 0),
        })
        leave.action_approve()

        work_entries = self.richard_emp.contract_ids._generate_work_entries(date(2015, 11, 10), date(2015, 11, 21))
        work_entries.action_validate()
        hours = (self.contract_cdd | self.contract_cdi)._get_work_hours(date(2015, 11, 10), date(2015, 11, 20))  # across two contracts
        sum_hours = sum(v for k, v in hours.items() if k in self.env.ref('hr_work_entry.work_entry_type_attendance').ids)
        self.assertEqual(sum_hours, 59, 'It should count 59 attendance hours')  # 24h first contract + 35h second contract

    def test_work_data_with_exceeding_interval(self):
        self.env['hr.work.entry'].create({
            'name': 'Attendance',
            'employee_id': self.richard_emp.id,
            'contract_id': self.contract_cdd.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'date_start': datetime(2015, 11, 9, 20, 0),
            'date_stop': datetime(2015, 11, 10, 7, 0)
        }).action_validate()
        self.env['hr.work.entry'].create({
            'name': 'Attendance',
            'employee_id': self.richard_emp.id,
            'contract_id': self.contract_cdd.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'date_start': datetime(2015, 11, 10, 21, 0),
            'date_stop': datetime(2015, 11, 11, 5, 0),
        }).action_validate()
        hours = self.contract_cdd._get_work_hours(date(2015, 11, 10), date(2015, 11, 10))
        sum_hours = sum(v for k, v in hours.items() if k in self.env.ref('hr_work_entry.work_entry_type_attendance').ids)
        self.assertAlmostEqual(sum_hours, 18, delta=0.01, msg='It should count 18 attendance hours')  # 8h normal day + 7h morning + 3h night

    def test_unpaid_amount(self):
        self.assertAlmostEqual(self.richard_payslip._get_unpaid_amount(), 0, places=2, msg="It should be paid the full wage")

        leave = self.env['hr.leave'].create({
            'name': 'Doctor Appointment',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type_unpaid.id,
            'date_from': date(2016, 1, 11),
            'date_to': date(2016, 1, 12),
        })
        leave.action_approve()

        work_entries = self.richard_emp.contract_ids._generate_work_entries(date(2016, 1, 1), date(2016, 2, 1))
        work_entries.action_validate()

        # Call _onchange_employee to compute worked_days_line_ids and get the updated unpaid amount
        self.richard_payslip._onchange_employee()
        # TBE: In master the Monetary field were not rounded because the currency_id wasn't computed yet.
        # The test was incorrect using the value 238.09, with 238.10 it is ok
        self.assertAlmostEqual(self.richard_payslip._get_unpaid_amount(), 238.10, delta=0.01, msg="It should be paid 238.10 less")

    def test_worked_days_amount_with_unpaid(self):
        leave = self.env['hr.leave'].create({
            'name': 'Doctor Appointment',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type.id,
            'date_from': date(2016, 1, 11),
            'date_to': date(2016, 1, 12),
        })
        leave.action_approve()

        leave_unpaid = self.env['hr.leave'].create({
            'name': 'Doctor Appointment',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type_unpaid.id,
            'date_from': date(2016, 1, 21),
            'date_to': date(2016, 1, 22),
        })
        leave_unpaid.action_approve()

        work_entries = self.richard_emp.contract_ids._generate_work_entries(date(2016, 1, 1), date(2016, 2, 1))
        work_entries.action_validate()

        # Call _onchange_employee to compute worked_days_line_ids
        self.richard_payslip._onchange_employee()
        work_days = self.richard_payslip.worked_days_line_ids

        self.assertAlmostEqual(sum(work_days.mapped('amount')), self.contract_cdi.wage - self.richard_payslip._get_unpaid_amount())

        leave_line = work_days.filtered(lambda l: l.code == self.work_entry_type_leave.code)
        self.assertAlmostEqual(leave_line.amount, 238.09, delta=0.01, msg="His paid time off must be paid 238.09")

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.amount, 0.0, places=2, msg="His unpaid time off must be paid 0.")

        attendance_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.work_entry_type_attendance').code)
        self.assertAlmostEqual(attendance_line.amount, 4523.81, delta=0.01, msg="His attendance must be paid 4523.81")

    def test_worked_days_with_unpaid(self):
        self.contract_cdi.resource_calendar_id = self.env.ref('resource.resource_calendar_std_38h')
        self.richard_emp.resource_calendar_id = self.env.ref('resource.resource_calendar_std_38h')

        leaves = self.env['hr.leave']

        # Create 2 hours upaid leave every day during 2 weeks
        for day in rrule(freq=DAILY, byweekday=[0, 1, 2, 3, 4], count=10, dtstart=datetime(2016, 2, 8)):
            start = day + timedelta(hours=13.6)
            end = day + timedelta(hours=15.6)
            leaves |= self.env['hr.leave'].create({
                'name': 'Unpaid Leave',
                'employee_id': self.richard_emp.id,
                'holiday_status_id': self.leave_type_unpaid.id,
                'date_from': start,
                'date_to': end,
            })
        leaves.action_approve()

        work_entries = self.richard_emp.contract_ids._generate_work_entries(date(2016, 1, 1), date(2016, 3, 31))
        work_entries.action_validate()

        self.richard_payslip_quarter._onchange_employee()
        work_days = self.richard_payslip_quarter.worked_days_line_ids

        leave_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.work_entry_type_attendance').code)
        self.assertAlmostEqual(leave_line.number_of_days, 62.5, places=2)

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.number_of_days, 2.5, places=2)

    def test_worked_days_16h_with_unpaid(self):
        self.contract_cdi.resource_calendar_id = self.calendar_16h
        self.richard_emp.resource_calendar_id = self.calendar_16h

        leaves = self.env['hr.leave']

        # Create 2 hours upaid leave every Thursday Evening during 5 weeks
        for day in rrule(freq=DAILY, byweekday=3, count=5, dtstart=datetime(2016, 2, 4)):
            start = day + timedelta(hours=12.5)
            end = day + timedelta(hours=14.5)
            leaves |= self.env['hr.leave'].create({
                'name': 'Unpaid Leave',
                'employee_id': self.richard_emp.id,
                'holiday_status_id': self.leave_type_unpaid.id,
                'date_from': start,
                'date_to': end,
            })
        leaves.action_approve()

        work_entries = self.richard_emp.contract_ids._generate_work_entries(date(2016, 1, 1), date(2016, 3, 31))
        work_entries.action_validate()

        self.richard_payslip_quarter._onchange_employee()
        work_days = self.richard_payslip_quarter.worked_days_line_ids

        leave_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.work_entry_type_attendance').code)
        self.assertAlmostEqual(leave_line.number_of_days, 49.5, places=2)

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.number_of_days, 2.5, places=2)

    def test_worked_days_38h_friday_with_unpaid(self):
        self.contract_cdi.resource_calendar_id = self.calendar_38h_friday_light
        self.richard_emp.resource_calendar_id = self.calendar_38h_friday_light

        leaves = self.env['hr.leave']

        # Create 4 hours (all work day) upaid leave every Friday during 5 weeks
        for day in rrule(freq=DAILY, byweekday=4, count=5, dtstart=datetime(2016, 2, 4)):
            start = day + timedelta(hours=7)
            end = day + timedelta(hours=11)
            leaves |= self.env['hr.leave'].create({
                'name': 'Unpaid Leave',
                'employee_id': self.richard_emp.id,
                'holiday_status_id': self.leave_type_unpaid.id,
                'date_from': start,
                'date_to': end,
            })
        leaves.action_approve()

        work_entries = self.richard_emp.contract_ids._generate_work_entries(date(2016, 1, 1), date(2016, 3, 31))
        work_entries.action_validate()

        self.richard_payslip_quarter._onchange_employee()
        work_days = self.richard_payslip_quarter.worked_days_line_ids

        leave_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.work_entry_type_attendance').code)
        self.assertAlmostEqual(leave_line.number_of_days, 62.5, places=2)

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.number_of_days, 2.5, places=2)

    def test_sum_catergory(self):
        self.richard_payslip.compute_sheet()
        self.richard_payslip.action_payslip_done()

        self.richard_payslip2 = self.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': self.richard_emp.id,
            'contract_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        self.richard_payslip2.compute_sheet()
        self.assertEqual(2800, self.richard_payslip2.line_ids.filtered(lambda x: x.code == 'SUMALW').total)
