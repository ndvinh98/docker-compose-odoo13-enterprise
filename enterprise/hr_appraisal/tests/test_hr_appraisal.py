# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestHrAppraisal(TransactionCase):
    """ Test used to check that when doing appraisal creation."""

    def setUp(self):
        super(TestHrAppraisal, self).setUp()
        self.HrEmployee = self.env['hr.employee']
        self.HrAppraisal = self.env['hr.appraisal']
        self.Request = self.env['request.appraisal']
        self.main_company = self.env.ref('base.main_company')

        group = self.env.ref('hr_appraisal.group_hr_appraisal_user').id
        self.user = self.env['res.users'].create({
            'name': 'Michael Hawkins',
            'login': 'test',
            'groups_id': [(6, 0, [group])],
        })

        self.env.ref('hr.employee_qdp').user_id.email = "demo@demo.com"
        self.hr_employee = self.HrEmployee.create(dict(
            name="Michael Hawkins",
            user_id=self.user.id,
            department_id=self.env.ref('hr.dep_rd').id,
            parent_id=self.env.ref('hr.employee_qdp').id,
            job_id=self.env.ref('hr.job_developer').id,
            work_location="Grand-Rosière",
            work_phone="+3281813700",
            work_email='michael@odoo.com',
            appraisal_by_manager=True,
            appraisal_manager_ids=[self.env.ref('hr.employee_al').id],
            appraisal_by_colleagues=True,
            appraisal_colleagues_ids=[self.env.ref('hr.employee_stw').id],
            appraisal_self=True,
            appraisal_date=date.today() + relativedelta(months=-12, days=5)
        ))
        self.env['ir.config_parameter'].sudo().set_param("hr_appraisal.appraisal_min_period", 6)
        self.env['ir.config_parameter'].sudo().set_param("hr_appraisal.appraisal_max_period", 12)
        self.env['ir.config_parameter'].sudo().set_param("hr_appraisal.appraisal_create_in_advance_days", 8)

    def test_hr_appraisal(self):
        # I create a new Employee with appraisal configuration.

        # I run the scheduler
        self.HrEmployee.run_employee_appraisal()  # cronjob

        # I check whether new appraisal is created for above employee or not
        appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertTrue(appraisals, "Appraisal not created")

        # I start the appraisal process by click on "Start Appraisal" button.
        appraisals.button_send_appraisal()

        # I check that state is "Appraisal Sent".
        self.assertEqual(appraisals.state, 'pending', "appraisal should be 'Appraisal Sent' state")
        # I check that "Final Interview Date" is set or not.
        #appraisals.write({'date_final_interview': str(datetime() + relativedelta(months=1))})
        event = self.env['calendar.event'].create({
            "name":"Appraisal Meeting",
            "start": datetime.now() + relativedelta(months=1),
            "stop":datetime.now() + relativedelta(months=1, hours=2),
            "duration":2,
            "allday": False,
            'res_id': appraisals.id,
            'res_model_id': self.env.ref('hr_appraisal.model_hr_appraisal').id
        })
        self.assertTrue(appraisals.date_final_interview, "Interview Date is not created")
        # I check whether final interview meeting is created or not
        self.assertTrue(appraisals.meeting_id, "Meeting is not linked")
        # I close this Apprisal
        appraisals.button_done_appraisal()
        # I check that state of Appraisal is done.
        self.assertEqual(appraisals.state, 'done', "Appraisal should be in done state")

    def test_appraisal_cron_on_employees_with_no_appraisal_date(self):
        # Appraisal date is not set when creating a new employee and this was causing the cron to never be executed on them
        hr_employee2 = self.HrEmployee.create({'name': "John Doe"})

        self.assertFalse(hr_employee2.appraisal_date, 'No appraisal date is set on a new employee')
        hr_employee2.run_employee_appraisal()
        self.assertEqual(hr_employee2.appraisal_date, date.today())

    def test_request_appraisal_too_early(self):
        self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() + relativedelta(months=1),
        })

        with self.assertRaises(ValidationError):
            self.HrAppraisal.with_user(self.user.id).create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today() + relativedelta(months=2),
            })

    def test_01_appraisal_generation(self):
        """
            Set appraisal date at the exact time it should be generated
            Run the cron and check the appraisal_date is set properly

            Run the cron again and check no more appraisals are created
        """
        self.hr_employee.appraisal_date = date.today() - relativedelta(months=12, days=-8)

        self.HrEmployee.run_employee_appraisal()
        appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertTrue(appraisals, "Appraisal not created")
        self.assertEqual(appraisals.date_close, date.today() + relativedelta(days=8))
        self.assertEqual(self.hr_employee.appraisal_date, date.today() + relativedelta(days=8))

        self.HrEmployee.run_employee_appraisal()
        appraisals_2 = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertEqual(len(appraisals), len(appraisals_2))

    def test_02_no_appraisal_generation(self):
        """
            Set appraisal date later then the time it should be generated
            Run the cron and check the appraisal is not created
        """
        self.hr_employee.appraisal_date = date.today() - relativedelta(months=12, days=-9)

        self.HrEmployee.run_employee_appraisal()
        appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertFalse(appraisals, "Appraisal created")

    def test_03_appraisal_generation_in_the_past(self):
        """
            Set appraisal date way before the time it should be generated
            Run the cron and check the appraisal is created with the proper
            close_date and appraisal date
        """
        self.hr_employee.appraisal_date = date.today() - relativedelta(months=24)

        self.HrEmployee.run_employee_appraisal()
        appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertTrue(appraisals, "Appraisal not created")
        self.assertEqual(appraisals.date_close, date.today() + relativedelta(days=8))
        self.assertEqual(self.hr_employee.appraisal_date, date.today() + relativedelta(days=8))

        self.HrEmployee.run_employee_appraisal()
        appraisals_2 = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertEqual(len(appraisals), len(appraisals_2))

    def test_04_check_appraisal_date_no_appraisal(self):
        """
            Set no appraisal date
            1) should take employee create date and generate no appraisal
        """
        self.hr_employee.appraisal_date = False
        self.HrEmployee.run_employee_appraisal()
        appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
        self.assertEqual(self.hr_employee.create_date.date(), self.hr_employee.appraisal_date)
        self.assertFalse(appraisals, "Appraisal created")

    def test_05_check_appraisal_date_appraisal_past_year(self):
        """
            Create an appraisal 11 month ago, after the max delay
            Set no appraisal date
            appraisal_date should take the date_close of the appraisal_created
        """
        past_appraisal = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() - relativedelta(months=11),
            'state': 'done'
        })
        self.hr_employee.appraisal_date = False
        self.HrEmployee.run_employee_appraisal()
        appraisals = self.HrAppraisal.search([
            ('employee_id', '=', self.hr_employee.id),
            ('id', 'not in', past_appraisal.ids)
        ])
        self.assertEqual(self.hr_employee.appraisal_date, past_appraisal.date_close)
        self.assertFalse(appraisals, "Appraisal created")

    def test_06_check_appraisal_date_appraisal_long_time_ago(self):
        """
            Create an appraisal 13 month ago, before the max delay
            Set no appraisal date
            appraisal_date should take the date_close of the appraisal_created
            then generate a new appraisal and set the appraisal_date
            of this new appraisal
        """
        past_appraisal = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() - relativedelta(months=13),
            'state': 'done'
        })
        self.hr_employee.appraisal_date = False
        self.HrEmployee.run_employee_appraisal()
        appraisals = self.HrAppraisal.search([
            ('employee_id', '=', self.hr_employee.id),
            ('id', 'not in', past_appraisal.ids)
        ])
        self.assertEqual(self.hr_employee.appraisal_date, date.today() + relativedelta(days=8))
        self.assertTrue(appraisals, "Appraisal not created")

    def test_07_check_manual_appraisal_set_appraisal_date(self):
        """
            Create manualy an appraisal with a date_close
            Check the appraisal_date is set properly
        """
        past_appraisal = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() + relativedelta(months=1),
            'state': 'new'
        })
        self.assertEqual(self.hr_employee.appraisal_date, date.today() + relativedelta(months=1))

    def test_08_request_appraisal_from_employee(self):
        """
            As manager request an appraisal with your employee
        """
        template_employee_id = self.env.ref('hr_appraisal.mail_template_appraisal_request').id
        Request = self.Request.with_context(active_model='hr.employee', active_id=self.hr_employee.id)
        default = Request.default_get([])
        self.assertEqual(default['template_id'], template_employee_id)
        default['deadline'] = date.today() + relativedelta(months=1)
        request = Request.create(default)
        request._onchange_template_id()
        request.action_invite()

        appraisals = self.HrAppraisal.search([
            ('employee_id', '=', self.hr_employee.id),
        ])
        self.assertTrue(appraisals, "Appraisal not created")
        self.assertTrue(self.hr_employee.appraisal_date, date.today() + relativedelta(months=1))

    def test_09_request_appraisal_from_user(self):
        """
            request an appraisal for yourself with your manager
        """
        template_employee_id = self.env.ref('hr_appraisal.mail_template_appraisal_request_from_employee').id
        Request = self.Request.with_context(active_model='res.users', active_id=self.hr_employee.user_id.id)
        default = Request.default_get([])
        self.assertEqual(default['template_id'], template_employee_id)
        #Check the recipient is the manager define on the employee
        self.assertEqual(default['recipient_id'], self.env.ref('hr.employee_qdp').user_id.partner_id.id)
        default.update({
            'deadline': date.today() + relativedelta(months=1),
        })
        request = Request.create(default)
        request._onchange_template_id()
        request.action_invite()

        appraisals = self.HrAppraisal.search([
            ('employee_id', '=', self.hr_employee.id),
        ])
        self.assertTrue(appraisals, "Appraisal not created")
        self.assertTrue(self.hr_employee.appraisal_date, date.today() + relativedelta(months=1))
