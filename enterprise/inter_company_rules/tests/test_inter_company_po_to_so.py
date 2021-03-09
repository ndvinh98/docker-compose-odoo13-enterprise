# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .common import TestInterCompanyRulesCommon
from odoo.tests import Form


class TestInterCompanyPurchaseToSale(TestInterCompanyRulesCommon):

    def generate_purchase_order(self, company, partner):
        """ Generate purchase order and confirm its state """
        purchase_order = Form(self.env['purchase.order'])
        purchase_order.partner_id = partner
        purchase_order.company_id = company
        purchase_order.currency_id = company.currency_id
        purchase_order = purchase_order.save()

        with Form(purchase_order) as po:
            with po.order_line.new() as line:
                line.name = 'Service'
                line.product_id = self.product_consultant
                line.price_unit = 450.0

        # Confirm Purchase order
        purchase_order.button_confirm()
        # Check purchase order state should be purchase.
        self.assertEquals(purchase_order.state, 'purchase', 'Purchase order should be in purchase state.')
        return purchase_order

    def validate_generated_sale_order(self, purchase_order, company, partner):
        """ Validate sale order which has been generated from purchase order
        and test its state, total_amount, product_name and product_quantity.
        """

        # Find related sale order based on client order reference.
        sale_order = self.env['sale.order'].search([('client_order_ref', '=', purchase_order.name)], limit=1)

        self.assertTrue(sale_order.state == "draft", "sale order should be in draft state.")
        self.assertTrue(sale_order.partner_id == company.partner_id, "Vendor does not correspond to Company %s." % company)
        self.assertTrue(sale_order.company_id == partner, "Applied company in created sale order is incorrect.")
        self.assertTrue(sale_order.amount_total == 450.0, "Total amount is incorrect.")
        self.assertTrue(sale_order.order_line[0].product_id == self.product_consultant, "Product in line is incorrect.")
        self.assertTrue(sale_order.order_line[0].name == 'Service', "Product name is incorrect.")
        self.assertTrue(sale_order.order_line[0].product_uom_qty == 1, "Product qty is incorrect.")
        self.assertTrue(sale_order.order_line[0].price_unit == 450, "Unit Price in line is incorrect.")

    def test_00_inter_company_sale_purchase(self):
        """ Configure "Sale/Purchase" option and then Create purchase order and find related
        sale order to related company and compare them.
        """

        # Generate purchase order in company A for company B
        self.company_b.update({
            'applicable_on': 'sale_purchase',
        })
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Check sale order is created in company B ( for company A )
        self.validate_generated_sale_order(purchase_order, self.company_a, self.company_b)
        # reset configuration of company B
        self.company_b.update({
            'applicable_on': False,
        })

        # Generate purchase order in company B for company A
        self.company_a.update({
            'applicable_on': 'sale_purchase',
        })
        purchase_order = self.generate_purchase_order(self.company_b, self.company_a.partner_id)
        # Check sale order is created in company A ( for company B )
        self.validate_generated_sale_order(purchase_order, self.company_b, self.company_a)
        # reset configuration of company A
        self.company_a.update({
            'applicable_on': False,
        })

    def test_01_inter_company_purchase_order_with_configuration(self):
        """ Configure only "purchase" option and then Create purchase order and find related
        sale order to related company and compare them.
        """

        # Generate purchase order in company A for company B
        self.company_b.update({
            'applicable_on': 'purchase',
        })
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Check sale order is created in company B ( for company A )
        self.validate_generated_sale_order(purchase_order, self.company_a, self.company_b)
        # reset configuration of company B
        self.company_b.update({
            'applicable_on': False,
        })

        # Generate purchase order in company B for company A
        self.company_a.update({
            'applicable_on': 'purchase',
        })
        purchase_order = self.generate_purchase_order(self.company_b, self.company_a.partner_id)
        # Check sale order is created in company A ( for company B )
        self.validate_generated_sale_order(purchase_order, self.company_b, self.company_a)
        # reset configuration  of company A
        self.company_a.update({
            'applicable_on': False,
        })

    def test_02_inter_company_purchase_order_without_configuration(self):
        """ Without any Configuration Create purchase order and try to find related
        sale order to related company.
        """

        # without any inter_company configuration generate purchase_order in company A for company B
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Find related sale order based on client order reference.
        sale_order = self.env['sale.order'].search([('client_order_ref', '=', purchase_order.name)], limit=1)
        self.assertTrue((not sale_order), "Sale order created for company B from Purchase order of company A without configuration")

        # without any inter_company configuration generate purchase_order in company B for company A
        purchase_order = self.generate_purchase_order(self.company_b, self.company_a.partner_id)
        # Find related sale order based on client order reference.
        sale_order = self.env['sale.order'].search([('client_order_ref', '=', purchase_order.name)], limit=1)
        self.assertTrue((not sale_order), "Sale order created for company A from Purchase order of company B without configuration")
