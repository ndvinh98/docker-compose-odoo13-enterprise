# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import SavepointCase
from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheetMultiCompanyNoChart
from datetime import datetime


class TestMultiCompanyCommon(TestCommonSaleTimesheetMultiCompanyNoChart):

    @classmethod
    def setUpClass(cls):
        super(TestMultiCompanyCommon, cls).setUpClass()
        cls.setUpEmployees()

        # adding groups to users to use through the various tests
        user_group_employee = cls.env.ref('base.group_user')
        user_project_group_employee = cls.env.ref('project.group_project_user')
        cls.user_employee.write({
            'groups_id': [(6, 0, [user_group_employee.id, user_project_group_employee.id])],
        })
        cls.user_employee_company_B.write({
            'groups_id': [(6, 0, [user_group_employee.id, user_project_group_employee.id])],
        })
        cls.user_manager.write({
            'groups_id': [(6, 0, [user_group_employee.id, user_project_group_employee.id])],
        })
        cls.user_manager_company_B.write({
            'groups_id': [(6, 0, [user_group_employee.id, user_project_group_employee.id])],
        })
        Project = cls.env['project.project'].with_context({'mail_create_nolog': True, 'tracking_disable': True})
        cls.fsm_company_a = Project.create({
            'name': 'FSM Company A',
            'alias_name': 'fsm+companya',
            'company_id': cls.env.company.id,
            'is_fsm': True,
            'allow_timesheets': True,
            'allow_billable': True,
            'timesheet_product_id': cls.env.ref('industry_fsm.fsm_time_product').id,
            'allow_material': True,
            'allow_quotations': True,
            'type_ids': [
                (0, 0, {
                    'name': 'New',
                    'sequence': 1,
                }),
                (0, 0, {
                    'name': 'Won',
                    'sequence': 10,
                })
            ]
        })

        Task = cls.env['project.task'].with_context({'mail_create_nolog': True, 'tracking_disable': True})
        cls.task_1 = Task.create({
            'name': 'Task 1 in Project A',
            'user_id': cls.user_employee.id,
            'partner_id': cls.partner_customer_usd.id,
            'project_id': cls.fsm_company_a.id
        })

        cls.task_2 = Task.create({
            'name': 'Task 2 in Project A',
            'user_id': cls.user_employee.id,
            'partner_id': cls.partner_customer_usd.id,
            'project_id': cls.fsm_company_a.id
        })

        values = {
            'task_id': cls.task_1.id,
            'project_id': cls.task_1.project_id.id,
            'date': datetime.now(),
            'name': 'test timesheet',
            'user_id': cls.user_employee.id,
            'unit_amount': 0.25,
        }
        cls.env['account.analytic.line'].create(values)

    def test_task(self):
        # This should not raise an error.
        self.task_1.with_context(allowed_company_ids=[self.env.company.id, self.company_B.id], company_id=self.company_B.id).action_fsm_view_material()

        self.assertFalse(self.task_1.fsm_done, "Task should not be validated")
        self.assertEqual(self.task_1.sale_order_id.state, 'draft', "Sale order should not be confirmed")
        # Validating a task while in another company should not impact the propagation of the company_id to the sale order
        self.task_1.with_user(self.user_manager).with_context(allowed_company_ids=[self.env.company.id, self.company_B.id], company_id=self.company_B.id).action_fsm_validate()
        self.assertTrue(self.task_1.fsm_done, "Task should be validated")
        self.assertEqual(self.task_1.sale_order_id.state, 'sale', "Sale order should be confirmed")
        self.assertEqual(self.task_1.sale_order_id.company_id.id, self.task_1.company_id.id, "The company of the sale order should be the same as the one from the task")
        # Generating an invoice from a task while in another company should not impact the propagation of the company_id to the invoice
        self.assertTrue(self.task_1.fsm_to_invoice, "Task should be invoiceable")
        # YTI This is supposed to be reintroduced after a fix from DBO See #42408
        # invoice_ctx = self.task_1.action_fsm_create_invoice()['context']
        # invoice_ctx['allowed_company_ids']=[self.env.company.id, self.company_B.id]
        # invoice_ctx['company_id']=self.company_B.id
        # invoice_wizard = self.env['sale.advance.payment.inv'].with_context(invoice_ctx).create({})
        # invoice_wizard.create_invoices()
        # self.assertFalse(self.task_1.fsm_to_invoice, "Task should not be invoiceable")
        # self.assertEqual(self.task_1.sale_order_id.invoice_ids[0].company_id.id, self.task_1.company_id.id, "The company of the invoice should be the same as the one from the task")
