# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.addons.web_grid.models.models import END_OF

from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheetNoChart


class TestSaleValidatedTimesheet(TestCommonSaleTimesheetNoChart):
    """ Test timesheet invoicing of "Approved Timesheets Only" with 2 service products that create a task in a new project.
                1. Create SO, add two SO line ordered service and delivered service and confirm it
                2. log some timesheet on task and validate it.
                3. create invoice
                4. log other timesheets
                5. create a second invoice
    """

    @classmethod
    def setUpClass(self):
        super(TestSaleValidatedTimesheet, self).setUpClass()
        # set up
        self.setUpEmployees()
        self.setUpServiceProducts()
        # create SO
        self.sale_order = self.env['sale.order'].with_context(tracking_disable=True).create({
            'company_id': self.env.company.id,
            'partner_id': self.partner_customer_usd.id,
            'partner_invoice_id': self.partner_customer_usd.id,
            'partner_shipping_id': self.partner_customer_usd.id,
            'pricelist_id': self.pricelist_usd.id,
        })
        self.ordered_so_line = self.env['sale.order.line'].with_context(tracking_disable=True).create({
            'name': self.product_order_timesheet3.name,
            'product_id': self.product_order_timesheet3.id,
            'product_uom_qty': 10,
            'product_uom': self.product_order_timesheet3.uom_id.id,
            'order_id': self.sale_order.id,
        })
        self.delivered_so_line = self.env['sale.order.line'].with_context(tracking_disable=True).create({
            'name': self.product_delivery_timesheet3.name,
            'product_id': self.product_delivery_timesheet3.id,
            'product_uom_qty': 10,
            'product_uom': self.product_delivery_timesheet3.uom_id.id,
            'order_id': self.sale_order.id,
        })

    def test_sale_validated_timesheet(self):
        # set invoiced_timesheet as "Approved timesheet only"
        self.env['ir.config_parameter'].sudo().set_param('sale.invoiced_timesheet', 'approved')
        #  confirm SO
        self.sale_order.action_confirm()

        project_1 = self.env['project.project'].search([('sale_order_id', '=', self.sale_order.id)])
        ordered_task = self.env['project.task'].search([('sale_line_id', '=', self.ordered_so_line.id)])
        delivered_task = self.env['project.task'].search([('sale_line_id', '=', self.delivered_so_line.id)])
        # check project, task and analytic account
        self.assertEqual(self.sale_order.tasks_count, 2, "Two task should have been created on SO confirmation")
        self.assertEqual(len(self.sale_order.project_ids), 1, "One project should have been created on SO confirmation")
        self.assertEqual(self.sale_order.analytic_account_id, project_1.analytic_account_id, "The created project should be linked to the analytic account of the SO")

        today = date.today()
        week_before = date.today() + relativedelta(weeks=-1)
        # log timesheet on task of delivered So line
        delivered_timesheet1 = self.env['account.analytic.line'].create({
            'name': 'Timesheet delivered 1',
            'project_id': delivered_task.project_id.id,
            'task_id': delivered_task.id,
            'unit_amount': 6,
            'employee_id': self.employee_user.id,
            'date': week_before,
        })
        delivered_timesheet2 = self.env['account.analytic.line'].create({
            'name': 'Timesheet delivered 2',
            'project_id': delivered_task.project_id.id,
            'task_id': delivered_task.id,
            'unit_amount': 4,
            'employee_id': self.employee_user.id,
            'date': today,
        })
        # log timesheet on task of ordered so line
        ordered_timesheet1 = self.env['account.analytic.line'].create({
            'name': 'Timesheet ordered 1',
            'project_id': ordered_task.project_id.id,
            'task_id': ordered_task.id,
            'unit_amount': 8,
            'employee_id': self.employee_user.id,
            'date': week_before,
        })
        ordered_timesheet2 = self.env['account.analytic.line'].create({
            'name': 'Timesheet ordered 2',
            'project_id': ordered_task.project_id.id,
            'task_id': ordered_task.id,
            'unit_amount': 2,
            'employee_id': self.employee_user.id,
            'date': today,
        })

        # check not any timesheet should be validated
        self.assertFalse(any([delivered_timesheet1.validated, delivered_timesheet2.validated, ordered_timesheet1.validated, ordered_timesheet2.validated]), 'Timesheet should not be validated')

        # Validate ordered and delivered some Timesheet
        timesheet_to_validate = delivered_timesheet1 | ordered_timesheet1
        validate_action = timesheet_to_validate.with_context(grid_anchor=date.today() - relativedelta(weeks=1)).action_validate_timesheet()
        wizard = self.env['timesheet.validation'].browse(validate_action['res_id'])
        wizard.action_validate()
        # check timesheet date on the employee
        end_of_week = (week_before + END_OF['week'])
        self.assertEquals(self.employee_user.timesheet_validated, end_of_week, 'validate timesheet date should be the end of the week')

        self.assertTrue(any([delivered_timesheet1.validated, ordered_timesheet1.validated]), 'Timesheet should be validated')
        # check timesheet is linked to SOL
        self.assertEqual(delivered_timesheet1.so_line.id, self.delivered_so_line.id, "The delivered timesheet should be linked to Delivered SOL")
        self.assertEqual(ordered_timesheet1.so_line.id, self.ordered_so_line.id, "The ordered timesheet should be linked to ordered SOL")
        # check delivered quantity on SOL
        self.assertEqual(self.ordered_so_line.qty_delivered, 8, 'Delivered quantity should be 8 as some timesheet is validated')
        self.assertEqual(self.delivered_so_line.qty_delivered, 6, 'Delivered quantity should be 6 as some timesheet is validated')

        # invoice SO
        invoice1 = self.sale_order._create_invoices()
        # check invoiced amount
        self.assertEqual(invoice1.amount_total, self.ordered_so_line.price_unit * 10 + self.delivered_so_line.price_unit * 6, 'Invoiced amount should be equal to Ordered SOL + Delivered SOL unit price * 6')
        # check timesheet is linked to invoice
        self.assertEqual(delivered_timesheet1.timesheet_invoice_id, invoice1, "The delivered timesheet should be linked to the invoice")
        self.assertFalse(ordered_timesheet1.timesheet_invoice_id, "The ordered timesheet should not be linked to the invoice, since we are in ordered quantity")

        # check invoiced quantity on sale order and on invoice
        ordered_invoice_line = self.ordered_so_line.invoice_lines.filtered(lambda line: line.move_id == invoice1)
        self.assertEqual(self.ordered_so_line.qty_invoiced, ordered_invoice_line.quantity, "The invoiced quantity should be same on sales order line and invoice line")
        delivered_invoice_line = self.delivered_so_line.invoice_lines.filtered(lambda line: line.move_id == invoice1)
        self.assertEqual(self.delivered_so_line.qty_invoiced, delivered_invoice_line.quantity, "The invoiced quantity should be same on sales order line and invoice line")

        # Validate remaining Timesheet
        timesheet_to_validate = delivered_timesheet2 | ordered_timesheet2
        validate_action = timesheet_to_validate.action_validate_timesheet()
        wizard = self.env['timesheet.validation'].browse(validate_action['res_id'])
        wizard.action_validate()

        self.assertTrue(any([delivered_timesheet2.validated, ordered_timesheet2.validated]), 'Timesheet should be validated')
        # check remaining timesheet is linked to SOL
        self.assertEqual(delivered_timesheet2.so_line.id, self.delivered_so_line.id, "The delivered timesheet should be linked to Delivered SOL")
        self.assertEqual(ordered_timesheet2.so_line.id, self.ordered_so_line.id, "The ordered timesheet should be linked to ordered SOL")
        # check delivered quantity on SOL
        self.assertEqual(self.ordered_so_line.qty_delivered, 10, 'All quantity should be delivered')
        self.assertEqual(self.delivered_so_line.qty_delivered, 10, 'All quantity should be delivered')

        # invoice remaining SO
        invoice2 = self.sale_order._create_invoices()

        # check invoiced amount
        self.assertEqual(invoice2.amount_total, self.delivered_so_line.price_unit * 4, 'Invoiced amount should be equal to Delivered SOL unit price * 4')
        self.assertEqual(invoice1.amount_total+invoice2.amount_total, self.ordered_so_line.price_unit * 10 + self.delivered_so_line.price_unit * 10, 'Invoiced amount should be equal to Ordered SOL + Delivered SOL')
        # check invoiced quantity on sale order and on invoice
        ordered_invoice_line2 = self.ordered_so_line.invoice_lines.filtered(lambda line: line.move_id == invoice2)
        self.assertFalse(ordered_invoice_line2, "For ordered quantity so line we already invoiced full quantity on previous invoice so it should not be invoied now")
        delivered_invoice_line2 = self.delivered_so_line.invoice_lines.filtered(lambda line: line.move_id == invoice2)
        self.assertEqual(self.delivered_so_line.qty_invoiced, delivered_invoice_line.quantity + delivered_invoice_line2.quantity, "The invoiced quantity should be same on sales order line and invoice line")
        # order should be fully invoiced
        self.assertEqual(self.sale_order.invoice_status, 'invoiced', "The SO invoice status should be fully invoiced")
