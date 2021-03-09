# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import fields

from odoo.addons.web_grid.models.models import END_OF
from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet
from odoo.exceptions import AccessError, ValidationError

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

class TestTimesheetValidation(TestCommonTimesheet):

    def setUp(self):
        super(TestTimesheetValidation, self).setUp()
        today = fields.Date.today()
        self.timesheet1 = self.env['account.analytic.line'].with_user(self.user_employee).create({
            'name': "my timesheet 1",
            'project_id': self.project_customer.id,
            'task_id': self.task1.id,
            'date': today,
            'unit_amount': 2.0,
        })
        self.timesheet2 = self.env['account.analytic.line'].with_user(self.user_employee).create({
            'name': "my timesheet 2",
            'project_id': self.project_customer.id,
            'task_id': self.task2.id,
            'date': today,
            'unit_amount': 3.11,
        })

    def test_timesheet_validation_user(self):
        """ Employee record its timesheets and Officer validate them. Then try to modify/delete it and get Access Error """
        # Officer validate timesheet of 'user_employee' through wizard
        timesheet_to_validate = self.timesheet1 | self.timesheet2
        validate_action = timesheet_to_validate.with_user(self.user_manager).action_validate_timesheet()
        wizard = self.env['timesheet.validation'].browse(validate_action['res_id'])
        wizard.action_validate()

        # Check validated date
        end_of_week = (datetime.now() + END_OF['week']).date()
        self.assertEquals(self.empl_employee.timesheet_validated, end_of_week, 'validate timesheet date should be the end of the week')

        # Employee can not modify validated timesheet
        with self.assertRaises(AccessError):
            self.timesheet1.with_user(self.user_employee).write({'unit_amount': 5})
        # Employee can not delete validated timesheet
        with self.assertRaises(AccessError):
            self.timesheet2.with_user(self.user_employee).unlink()
        # Employee can not create new timesheet in the validated period
        with self.assertRaises(AccessError):
            last_month = fields.Date.to_string(datetime.now() - relativedelta(months=1))
            self.env['account.analytic.line'].with_user(self.user_employee).create({
                'name': "my timesheet 3",
                'project_id': self.project_customer.id,
                'task_id': self.task2.id,
                'date': last_month,
                'unit_amount': 2.5,
            })

        # Employee can still create timesheet after validated date
        next_month = fields.Date.to_string(datetime.now() + relativedelta(months=1))
        timesheet4 = self.env['account.analytic.line'].with_user(self.user_employee).create({
            'name': "my timesheet 4",
            'project_id': self.project_customer.id,
            'task_id': self.task2.id,
            'date': next_month,
            'unit_amount': 2.5,
        })
        # And can still update non validated timesheet
        timesheet4.write({'unit_amount': 7})

    def test_timesheet_validation_manager(self):
        """ Officer can see timesheets and modify the ones of other employees """
       # Officer validate timesheet of 'user_employee' through wizard
        timesheet_to_validate = self.timesheet1 | self.timesheet2
        validate_action = timesheet_to_validate.with_user(self.user_manager).action_validate_timesheet()
        wizard = self.env['timesheet.validation'].browse(validate_action['res_id'])
        wizard.action_validate()

        # manager modify validated timesheet
        self.timesheet1.with_user(self.user_manager).write({'unit_amount': 5})

    def _test_next_date(self, now, result, delay, interval):

        def _now(*args, **kwargs):
            return now

        # To allow testing

        patchers = [patch('odoo.fields.Datetime.now', _now)]

        for p in patchers:
            p.start()

        self.user_manager.company_id.write({
            'timesheet_mail_manager_interval': interval,
            'timesheet_mail_manager_delay': delay,
        })

        self.assertEquals(result, self.user_manager.company_id.timesheet_mail_manager_nextdate)

        for p in patchers:
            p.stop()

    def test_timesheet_next_date_reminder_neg_delay(self):

        result = datetime(2020, 4, 23, 8, 8, 15)
        now = datetime(2020, 4, 22, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 4, 30, 8, 8, 15)
        now = datetime(2020, 4, 23, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 4, 24, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 4, 25, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 4, 27, 8, 8, 15)
        now = datetime(2020, 4, 26, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

        result = datetime(2020, 5, 28, 8, 8, 15)
        now = datetime(2020, 4, 27, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 4, 28, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 4, 29, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

        result = datetime(2020, 2, 27, 8, 8, 15)
        now = datetime(2020, 2, 26, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 3, 5, 8, 8, 15)
        now = datetime(2020, 2, 27, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 2, 28, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 2, 29, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 2, 26, 8, 8, 15)
        now = datetime(2020, 2, 25, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

        result = datetime(2020, 3, 28, 8, 8, 15)
        now = datetime(2020, 2, 26, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 2, 27, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 2, 28, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
