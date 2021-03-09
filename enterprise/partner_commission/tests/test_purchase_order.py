# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import fields
from odoo.tools import format_date
from odoo.tests.common import Form, tagged
from odoo.addons.partner_commission.tests.setup import Line, Spec, TestCommissionsSetup


@tagged('commission_purchase')
class TestPurchaseOrder(TestCommissionsSetup):
    def test_automatic_confirm(self):
        """Only purchase orders within the frequency date range should be confirmed.
        Standard purchase orders should be untouched."""
        # Setup.
        self.company.commission_automatic_po_frequency = 'weekly'
        self.referrer.grade_id = self.learning
        self.referrer._onchange_grade_id()

        # Helper.
        def make_po(days_offset=0):
            inv = self.purchase(Spec(self.gold, [Line(self.crm, 1)]))
            po = inv.commission_po_line_id.order_id
            po.date_order = fields.Date.add(fields.Date.today(), days=days_offset)
            return po

        # Stub today's date.
        def today(*args, **kwargs):
            return fields.Date.to_date('2020-01-06')

        # Case: OK.
        with patch('odoo.fields.Date.today', today):
            po = make_po(days_offset=-1)
            self.env['purchase.order']._cron_confirm_purchase_orders()
            self.assertEqual(po.state, 'purchase')

        # Case: NOK: standard purchase order.
        # Should not be confirmed because it's not a commission purchase: commission_po_line_id is not set on the account.move.
        with patch('odoo.fields.Date.today', today):
            po = self.env['purchase.order'].create({
                'partner_id': self.customer.id,
                'company_id': self.company.id,
                'currency_id': self.company.currency_id.id,
                'date_order': fields.Date.subtract(fields.Date.today(), days=1),
            })
            self.env['purchase.order']._cron_confirm_purchase_orders()
            self.assertEqual(po.state, 'draft')

    def test_vendor_bill_description_multi_line_format(self):
        """Description text on vendor bill should have the following format:

        Commission on {{move.name}}, {{move.partner_id.name}}, {{move.amount_untaxed}} €
        {{subscription.code}}, from {{date_from}} to {{subscription.recurring_next_date}}
        """
        self.referrer.commission_plan_id = self.gold_plan
        self.referrer.grade_id = self.gold

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.partner_invoice_id = self.customer
        form.partner_shipping_id = self.customer
        form.referrer_id = self.referrer

        # Testing same rules, with cap reached, are grouped together.
        with form.order_line.new() as line:
            line.name = self.worker.name
            line.product_id = self.worker
            line.product_uom_qty = 20

        so = form.save()
        so.pricelist_id = self.eur_20
        so.action_confirm()

        inv = so._create_invoices()
        inv.name = 'INV/12345/0001'
        inv.post()
        self._pay_invoice(inv)

        sub = so.mapped('order_line.subscription_id')
        date_to = sub.recurring_next_date
        date_from = fields.Date.subtract(date_to, years=1)

        expected = f"""Commission on INV/12345/0001, Customer, 2,000.00 €
{sub.code}, from {format_date(self.env, date_from)} to {format_date(self.env, date_to)}"""
        self.assertEqual(inv.commission_po_line_id.name, expected)
