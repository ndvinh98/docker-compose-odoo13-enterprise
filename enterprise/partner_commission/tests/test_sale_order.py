# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import Form, tagged
from odoo.addons.partner_commission.tests.setup import TestCommissionsSetup


@tagged('commission_sale')
class TestSaleOrder(TestCommissionsSetup):
    def test_referrer_commission_plan_changed(self):
        """When the referrer's commission plan changes, its new commission plan should be set on the sale order."""
        self.referrer.commission_plan_id = self.gold_plan

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer
        so = form.save()

        self.assertEqual(so.commission_plan_id, self.gold_plan)

        # Update referrer's commission plan.
        self.referrer.commission_plan_id = self.silver_plan
        self.assertEqual(so.commission_plan_id, self.silver_plan)

    def test_referrer_grade_changed(self):
        """When the referrer's grade changes, its new commission plan should be set on the sale order."""
        self.referrer.grade_id = self.gold
        self.referrer._onchange_grade_id()

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer
        so = form.save()

        # Demote the referrer to silver.
        self.referrer.grade_id = self.silver
        self.referrer._onchange_grade_id()
        self.assertEqual(so.commission_plan_id, self.silver_plan)

    def test_so_data_forwarded_to_sub(self):
        """Some data should be forwarded from the sale order to the subscription."""
        self.referrer.commission_plan_id = self.gold_plan

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer

        with form.order_line.new() as line:
            line.name = self.worker.name
            line.product_id = self.worker
            line.product_uom_qty = 1

        so = form.save()
        so.action_confirm()
        sub = so.order_line.mapped('subscription_id')

        self.assertEqual(sub.referrer_id, so.referrer_id)
        self.assertEqual(sub.commission_plan_id, so.commission_plan_id)

        # check that inverse field is working
        so.commission_plan_id = self.silver_plan
        self.assertEqual(sub.commission_plan_id, self.silver_plan)
        self.assertEqual(sub.commission_plan_frozen, True)

        # revert to gold commission plan: should stuck to silver
        so.commission_plan_id = self.gold_plan
        self.assertEqual(sub.commission_plan_id, self.silver_plan)
        self.assertEqual(sub.commission_plan_frozen, True)

    def test_so_data_forwarded_to_invoice(self):
        """Some data should be forwarded from the sale order to the invoice."""
        self.referrer.commission_plan_id = self.gold_plan

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer

        with form.order_line.new() as line:
            line.name = self.worker.name
            line.product_id = self.worker
            line.product_uom_qty = 1

        so = form.save()
        so.action_confirm()
        sub = so.order_line.mapped('subscription_id')

        inv = self.env['account.move'].create(sub._prepare_invoice())

        self.assertEqual(inv.referrer_id, so.referrer_id)

    def test_compute_commission(self):
        self.referrer.commission_plan_id = self.gold_plan

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer

        with form.order_line.new() as line:
            line.name = self.worker.name
            line.product_id = self.worker
            line.product_uom_qty = 2

        so = form.save()
        so.pricelist_id = self.eur_20
        so.action_confirm()

        self.assertEqual(so.commission, 150)
