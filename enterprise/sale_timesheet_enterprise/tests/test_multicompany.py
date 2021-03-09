# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheetMultiCompanyNoChart


class TestSaleTimesheetEnterpriseMultiCompany(TestCommonSaleTimesheetMultiCompanyNoChart):

    @classmethod
    def setUpClass(cls):
        super(TestSaleTimesheetEnterpriseMultiCompany, cls).setUpClass()

        cls.setUpServiceProducts()

        Project = cls.env['project.project'].with_context(tracking_disable=True)
        cls.project_billable_tasks = Project.create({
            'name': "Billable on tasks",
            'company_id': cls.env.company.id,
            'allow_billable': 'yes',
            'partner_id': False,
        })

        Task = cls.env['project.task']
        cls.task = Task.with_context(default_project_id=cls.project_billable_tasks.id).create({
            'name': 'first task',
            'partner_id': cls.partner_customer_usd.id,
            'planned_hours': 10,
        })

    def test_taskBillable(self):
        wizard = self.env['project.task.create.sale.order'].with_context(allowed_company_ids=[self.env.company.id, self.company_B.id], company_id=self.company_B.id, active_id=self.task.id, active_model='project.task').create({
            'product_id': self.product_delivery_timesheet3.id
        })

        action = wizard.action_create_sale_order()
        sale_order = self.env['sale.order'].browse(action['res_id'])

        self.assertEqual(sale_order.company_id.id, self.task.company_id.id, "The company of the sale order should be the same as the one from the task")
