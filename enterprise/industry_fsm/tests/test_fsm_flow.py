# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from dateutil.relativedelta import relativedelta
from datetime import datetime
from odoo.exceptions import UserError, AccessError
from odoo.tests import common

class TestFsmFlow(common.TransactionCase):

    def setUp(self):
        super(TestFsmFlow, self).setUp()

        self.partner_1 = self.env.ref('base.res_partner_1')

        self.project_user = self.env['res.users'].create({
            'name': 'Armande Project_user',
            'login': 'Armande',
            'email': 'armande.project_user@example.com',
            'groups_id': [(6, 0, [self.env.ref('project.group_project_user').id])]
        })

        self.fsm_project = self.env.ref('industry_fsm.fsm_project')

        self.product_ordered = self.env.ref('product.product_product_24')
        self.product_delivered = self.env.ref('product.product_product_25')

        self.task = self.env['project.task'].with_context({'mail_create_nolog': True}).create({
            'name': 'Fsm task',
            'user_id': self.project_user.id,
            'project_id': self.fsm_project.id})



    def test_fsm_flow(self):

        # material
        self.assertFalse(self.task.material_line_product_count, "No product should be linked to a new task")
        with self.assertRaises(UserError, msg='Should not be able to get to material without customer set'):
            self.task.action_fsm_view_material()
        self.task.write({'partner_id': self.partner_1.id})
        self.assertFalse(self.task.fsm_to_invoice, "Nothing should be invoiceable on task")
        self.task.with_user(self.project_user).action_fsm_view_material()
        self.product_ordered.with_user(self.project_user).with_context({'fsm_task_id': self.task.id}).fsm_add_quantity()
        self.assertEqual(self.task.material_line_product_count, 1, "1 product should be linked to the task")
        self.assertEqual(self.task.material_line_total_price, self.product_ordered.list_price)
        self.product_ordered.with_user(self.project_user).with_context({'fsm_task_id': self.task.id}).fsm_add_quantity()
        self.assertEqual(self.task.material_line_product_count, 2, "2 product should be linked to the task")
        self.assertEqual(self.task.material_line_total_price, 2 * self.product_ordered.list_price)
        self.product_delivered.with_user(self.project_user).with_context({'fsm_task_id': self.task.id}).fsm_add_quantity()
        self.assertEqual(self.task.material_line_product_count, 3, "3 products should be linked to the task")
        self.assertEqual(self.task.material_line_total_price, 2 * self.product_ordered.list_price + self.product_delivered.list_price)
        self.product_delivered.with_user(self.project_user).with_context({'fsm_task_id': self.task.id}).fsm_remove_quantity()

        self.assertEqual(self.task.material_line_product_count, 2, "2 product should be linked to the task")

        self.assertFalse(self.task.sale_order_id.mapped('order_line').filtered(lambda l: l.product_id.id == self.product_delivered.id), "There should not be any order line left for removed product on task")

        self.product_delivered.with_user(self.project_user).with_context({'fsm_task_id': self.task.id}).fsm_add_quantity()

        self.assertEqual(self.task.material_line_product_count, 3, "3 product should be linked to the task")

        # timesheet
        values = {
            'task_id': self.task.id,
            'project_id': self.task.project_id.id,
            'date': datetime.now(),
            'name': 'test timesheet',
            'user_id': self.env.uid,
            'unit_amount': 0.25,
        }
        self.env['account.analytic.line'].create(values)
        self.assertEqual(self.task.material_line_product_count, 3, "Timesheet should not appear in material")

        # validation and SO
        self.assertFalse(self.task.fsm_done, "Task should not be validated")
        self.assertEqual(self.task.sale_order_id.state, 'draft', "Sale order should not be confirmed")
        self.task.with_user(self.project_user).action_fsm_validate()
        self.assertTrue(self.task.fsm_done, "Task should be validated")
        self.assertEqual(self.task.sale_order_id.state, 'sale', "Sale order should be confirmed")

        # invoice
        self.assertTrue(self.task.fsm_to_invoice, "Task should be invoiceable")
        invoice_ctx = self.task.action_fsm_create_invoice()['context']
        invoice_wizard = self.env['sale.advance.payment.inv'].with_context(invoice_ctx).create({})
        invoice_wizard.create_invoices()
        self.assertFalse(self.task.fsm_to_invoice, "Task should not be invoiceable")


        # quotation
        self.assertFalse(self.task.quotation_count, "No quotation should be linked to a new task")
        quotation_ctx = self.task.action_fsm_create_quotation()['context']
        quotation = self.env['sale.order'].with_context(quotation_ctx).create({'partner_id': self.task.partner_id.id})
        self.task._compute_quotation_count() # forced to compute manually because no 'depends' set on that method (no direct link to the task)
        self.assertEqual(self.task.quotation_count, 1, "1 quotation should be linked to the task")
        self.assertEqual(self.task.action_fsm_view_quotations()['res_id'], quotation.id, "Created quotation id should be in the action")

    def test_planning_overlap(self):
        task_A = self.env['project.task'].create({
            'name': 'Fsm task 1',
            'user_id': self.project_user.id,
            'project_id': self.fsm_project.id,
            'planned_date_begin': datetime.now(),
            'planned_date_end': datetime.now() + relativedelta(hours=4)
        })
        task_B = self.env['project.task'].create({
            'name': 'Fsm task 2',
            'user_id': self.project_user.id,
            'project_id': self.fsm_project.id,
            'planned_date_begin': datetime.now() + relativedelta(hours=2),
            'planned_date_end': datetime.now() + relativedelta(hours=6)
        })
        task_C = self.env['project.task'].create({
            'name': 'Fsm task 2',
            'user_id': self.project_user.id,
            'project_id': self.fsm_project.id,
            'planned_date_begin': datetime.now() + relativedelta(hours=5),
            'planned_date_end': datetime.now() + relativedelta(hours=7)
        })
        task_D = self.env['project.task'].create({
            'name': 'Fsm task 2',
            'user_id': self.project_user.id,
            'project_id': self.fsm_project.id,
            'planned_date_begin': datetime.now() + relativedelta(hours=8),
            'planned_date_end': datetime.now() + relativedelta(hours=9)
        })
        self.assertEqual(task_A.planning_overlap, 1, "One task should be overlapping with task_A")
        self.assertEqual(task_B.planning_overlap, 2, "Two tasks should be overlapping with task_B")
        self.assertFalse(task_D.planning_overlap, "No task should be overlapping with task_D")
