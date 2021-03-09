# # -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from unittest.mock import patch
import pytz

from odoo.fields import Datetime, Date
from odoo.tests.common import tagged, TransactionCase
from odoo.addons.hr_payroll.models.hr_work_entry import WorkIntervals
from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('work_entry')
class TestWorkEntry(TestPayslipBase):
    def setUp(self):
        super(TestWorkEntry, self).setUp()
        self.tz = pytz.timezone(self.richard_emp.tz)
        self.start = datetime(2015, 11, 1, 1, 0, 0)
        self.end = datetime(2015, 11, 30, 23, 59, 59)
        self.resource_calendar_id = self.env['resource.calendar'].create({'name': 'Zboub'})
        contract = self.env['hr.contract'].create({
            'date_start': self.start.date() - relativedelta(days=5),
            'name': 'dodo',
            'resource_calendar_id': self.resource_calendar_id.id,
            'wage': 1000,
            'employee_id': self.richard_emp.id,
            'structure_type_id': self.structure_type.id,
            'state': 'open',
            'date_generated_from': self.end.date() + relativedelta(days=5),
        })
        self.richard_emp.resource_calendar_id = self.resource_calendar_id
        self.richard_emp.contract_id = contract

    def test_no_duplicate(self):
        self.richard_emp.generate_work_entries(self.start, self.end)
        pou1 = self.env['hr.work.entry'].search_count([])
        self.richard_emp.generate_work_entries(self.start, self.end)
        pou2 = self.env['hr.work.entry'].search_count([])
        self.assertEqual(pou1, pou2, "Work entries should not be duplicated")

    def test_work_entry(self):
        self.richard_emp.generate_work_entries(self.start, self.end)
        attendance_nb = len(self.resource_calendar_id._attendance_intervals_batch(self.start.replace(tzinfo=pytz.utc), self.end.replace(tzinfo=pytz.utc))[False])
        work_entry_nb = self.env['hr.work.entry'].search_count([
            ('employee_id', '=', self.richard_emp.id),
            ('date_start', '>=', self.start),
            ('date_stop', '<=', self.end)])
        self.assertEqual(attendance_nb, work_entry_nb, "One work_entry should be generated for each calendar attendance")

    def test_approve_multiple_day_work_entry(self):
        start = datetime(2015, 11, 1, 9, 0, 0)
        end = datetime(2015, 11, 3, 18, 0, 0)

        work_entry = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'contract_id': self.richard_emp.contract_id.id,
            'date_start': start,
            'date_stop': end,
            'work_entry_type_id': self.work_entry_type.id,
        })
        work_entry.action_validate()
        work_entries = self.env['hr.work.entry'].search([('employee_id', '=', self.richard_emp.id)])
        self.assertTrue(all((b.state == 'validated' for b in work_entries)), "Work entries should be approved")

    def test_validate_conflict_work_entry(self):
        start = datetime(2015, 11, 1, 9, 0, 0)
        end = datetime(2015, 11, 1, 13, 0, 0)
        work_entry1 = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'contract_id': self.richard_emp.contract_id.id,
            'date_start': start,
            'date_stop': end + relativedelta(hours=5),
        })
        self.env['hr.work.entry'].create({
            'name': '2',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'contract_id': self.richard_emp.contract_id.id,
            'date_start': start + relativedelta(hours=3),
            'date_stop': end,
        })
        self.assertFalse(work_entry1.action_validate(), "It should not validate work_entries conflicting with others")
        self.assertEqual(work_entry1.state, 'conflict')
        self.assertNotEqual(work_entry1.state, 'validated')

    def test_validate_non_approved_leave_work_entry(self):
        work_entry1 = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.work_entry_type_leave.id,
            'contract_id': self.richard_emp.contract_id.id,
            'date_start': self.start,
            'date_stop': self.end,
        })
        self.env['hr.leave'].create({
            'name': 'Doctor Appointment',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type.id,
            'date_from': self.start - relativedelta(days=1),
            'date_to': self.start + relativedelta(days=1),
            'number_of_days': 2,
        })
        self.assertFalse(work_entry1.action_validate(), "It should not validate work_entries conflicting with non approved leaves")
        self.assertEqual(work_entry1.state, 'conflict')

    def test_validate_undefined_work_entry(self):
        work_entry1 = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'contract_id': self.richard_emp.contract_id.id,
            'date_start': self.start,
            'date_stop': self.end,
        })
        self.assertFalse(work_entry1.action_validate(), "It should not validate work_entries without a type")
        self.assertEqual(work_entry1.state, 'conflict', "It should change to conflict state")
        work_entry1.work_entry_type_id = self.work_entry_type
        self.assertTrue(work_entry1.action_validate(), "It should validate work_entries")

    def test_refuse_leave_work_entry(self):
        start = datetime(2015, 11, 1, 9, 0, 0)
        end = datetime(2015, 11, 3, 13, 0, 0)
        leave = self.env['hr.leave'].create({
            'name': 'Doctor Appointment',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type.id,
            'date_from': start,
            'date_to': start + relativedelta(days=1),
            'number_of_days': 2,
        })
        work_entry = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'contract_id': self.richard_emp.contract_id.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date_start': start,
            'date_stop': end,
            'leave_id': leave.id
        })
        work_entry.action_validate()
        self.assertEqual(work_entry.state, 'conflict', "It should have an error (conflicting leave to approve")
        leave.action_refuse()
        self.assertNotEqual(work_entry.state, 'conflict', "It should not have an error")

    def test_time_normal_work_entry(self):
        # Normal attendances (global to all employees)
        work_entries = self.richard_emp.contract_id._generate_work_entries(self.start, self.end)
        work_entries.action_validate()
        hours = self.richard_emp.contract_id._get_work_hours(self.start, self.end)
        sum_hours = sum(v for k, v in hours.items() if k in self.env.ref('hr_work_entry.work_entry_type_attendance').ids)

        self.assertEqual(sum_hours, 168.0)

    def test_time_extra_work_entry(self):
        start = datetime(2015, 11, 1, 10, 0, 0)
        end = datetime(2015, 11, 1, 17, 0, 0)
        work_entry = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'contract_id': self.richard_emp.contract_id.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date_start': start,
            'date_stop': end,
        })
        work_entry.action_validate()

        work_entries = self.richard_emp.contract_id._generate_work_entries(self.start, self.end)
        work_entries.action_validate()
        hours = self.richard_emp.contract_id._get_work_hours(self.start, self.end)
        sum_hours = sum(v for k, v in hours.items() if k in self.work_entry_type.ids)

        self.assertEqual(sum_hours, 7.0)

    def test_time_week_leave_work_entry(self):
        # /!\ this is a week day => it exists an calendar attendance at this time
        start = datetime(2015, 11, 2, 10, 0, 0)
        end = datetime(2015, 11, 2, 17, 0, 0)
        leave = self.env['hr.leave'].create({
            'name': '1leave',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type.id,
            'date_from': start,
            'date_to': end,
        })
        leave.action_validate()

        work_entries = self.richard_emp.contract_id._generate_work_entries(self.start, self.end)
        work_entries.action_validate()
        hours = self.richard_emp.contract_id._get_work_hours(self.start, self.end)
        sum_hours = sum(v for k, v in hours.items() if k in self.work_entry_type_leave.ids)

        self.assertEqual(sum_hours, 5.0, "It should equal the number of hours richard should have worked")

    def test_payslip_generation_with_extra_work(self):
        # /!\ this is in the weekend (Sunday) => no calendar attendance at this time
        start = datetime(2015, 11, 1, 10, 0, 0)
        end = datetime(2015, 11, 1, 17, 0, 0)
        work_entries = self.richard_emp.contract_id._generate_work_entries(start, end + relativedelta(days=2))
        work_entries.action_validate()

        work_entry = self.env['hr.work.entry'].create({
            'name': 'Extra',
            'employee_id': self.richard_emp.id,
            'contract_id': self.richard_emp.contract_id.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date_start': start,
            'date_stop': end,
        })
        work_entry.action_validate()
        payslip_wizard = self.env['hr.payslip.employees'].create({'employee_ids': [(4, self.richard_emp.id)]})
        payslip_wizard.with_context({
            'default_date_start': Date.to_string(start),
            'default_date_end': Date.to_string(end + relativedelta(days=1))
            }).compute_sheet()
        payslip = self.env['hr.payslip'].search([('employee_id', '=', self.richard_emp.id)])
        work_line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == self.env.ref('hr_work_entry.work_entry_type_attendance')) # From default calendar.attendance
        leave_line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == self.work_entry_type)

        self.assertTrue(work_line, "It should have a work line in the payslip")
        self.assertTrue(leave_line, "It should have an extra work line in the payslip")
        self.assertEqual(work_line.number_of_hours, 8.0, "It should have 8 hours of work")  # Monday
        self.assertEqual(leave_line.number_of_hours, 7.0, "It should have 5 hours of extra work")  # Sunday

    def test_outside_calendar(self):
        """ Test leave work entries outside schedule are conflicting """
        # Outside but not a leave
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 3, 0), datetime(2018, 10, 10, 4, 0))
        # Outside and a leave
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 1, 0), datetime(2018, 10, 10, 2, 0), work_entry_type=self.work_entry_type_leave)
        # Overlapping and a leave
        work_entry_3 = self.create_work_entry(datetime(2018, 10, 10, 7, 0), datetime(2018, 10, 10, 10, 0), work_entry_type=self.work_entry_type_leave)
        # Overlapping and not a leave
        work_entry_4 = self.create_work_entry(datetime(2018, 10, 10, 11, 0), datetime(2018, 10, 10, 13, 0))
        (work_entry_1 | work_entry_2 | work_entry_3 | work_entry_4)._mark_leaves_outside_schedule()
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertNotEqual(work_entry_3.state, 'conflict', "It should not conflict")
        self.assertNotEqual(work_entry_4.state, 'conflict', "It should not conflict")

    def test_write_conflict(self):
        """ Test updating work entries dates recomputes conflicts """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 12, 0), datetime(2018, 10, 10, 18, 0))
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertNotEqual(work_entry_2.state, 'conflict', "It should not conflict")
        work_entry_1.date_stop = datetime(2018, 10, 10, 14, 0)
        self.assertEqual(work_entry_1.state, 'conflict', "It should conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

        work_entry_1.date_stop = datetime(2018, 10, 10, 12, 0)  # cancel conflict
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should no longer conflict")
        self.assertNotEqual(work_entry_2.state, 'conflict', "It should no longer conflict")

    def test_write_move(self):
        """ Test completely moving a work entry recomputes conflicts """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 18, 9, 0), datetime(2018, 10, 18, 12, 0))
        work_entry_3 = self.create_work_entry(datetime(2018, 10, 18, 10, 0), datetime(2018, 10, 18, 12, 0))
        work_entry_2.write({
            'date_start': datetime(2018, 10, 10, 9, 0),
            'date_stop': datetime(2018, 10, 10, 10, 0),
        })
        self.assertEqual(work_entry_1.state, 'conflict')
        self.assertEqual(work_entry_2.state, 'conflict')
        self.assertNotEqual(work_entry_3.state, 'conflict')

    def test_create_conflict(self):
        """ Test creating a work entry recomputes conflicts """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0))
        self.assertEqual(work_entry_1.state, 'conflict', "It should conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

    def test_unarchive_conflict(self):
        """ Test archive/unarchive a work entry recomputes conflicts """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0))
        work_entry_2.active = False
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertEqual(work_entry_2.state, 'cancelled', "It should be cancelled")
        work_entry_2.active = True
        self.assertEqual(work_entry_1.state, 'conflict', "It should conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

    def test_validated_no_conflict(self):
        """ Test validating a work entry removes the conflict """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        work_entry_1.state = 'validated'
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0))
        self.assertEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

    def test_disable_multi_company_rule(self):
        """ Test that the work entry generation still work if
            the contract is not on the same company than
            the employee (Internal Use Case)
            So when generating the work entries in Belgium,
            there is an issue when accessing to the time off
            in Hong Kong.
        """
        company = self.env['res.company'].create({'name': 'Another Company'})

        employee = self.env['hr.employee'].create({
            'name': 'New Employee',
            'company_id': company.id,
        })

        contract = self.env['hr.contract'].create({
            'name': 'Employee Contract',
            'employee_id': employee.id,
            'date_start': Date.from_string('2015-01-01'),
            'state': 'open',
            'company_id': self.env.ref('base.main_company').id,
            'wage': 4000,
        })

        leave_type = self.env['hr.leave.type'].create({
            'name': 'Sick',
            'request_unit': 'hour',
            'validation_type': 'both',
            'allocation_type': 'no',
            'company_id': company.id,
        })
        leave1 = self.env['hr.leave'].create({
            'name': 'Sick 1 week during christmas snif',
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'date_from': Datetime.from_string('2019-12-23 06:00:00'),
            'date_to': Datetime.from_string('2019-12-27 20:00:00'),
            'number_of_days': 5,
        })
        leave1.action_approve()
        leave1.action_validate()

        # The work entries generation shouldn't raise an error

        user = self.env['res.users'].create({
            'name': 'Classic User',
            'login': 'Classic User',
            'company_id': self.env.ref('base.main_company').id,
            'company_ids': self.env.ref('base.main_company').ids,
            'groups_id': [(6, 0, [self.env.ref('hr_payroll.group_hr_payroll_user').id, self.env.ref('base.group_user').id])],
        })
        self.env['hr.employee'].with_user(user).generate_work_entries('2019-12-01', '2019-12-31')
