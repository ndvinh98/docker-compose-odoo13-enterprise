# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests.common import Form, tagged
from odoo.addons.partner_commission.tests.setup import Line, Spec, TestCommissionsSetup


@tagged('commission')
class TestCommissions(TestCommissionsSetup):

    def test_commissions(self):
        """Commissions should be computed based on matching rules."""
        specs = [
            # learning: EUR
            Spec(self.learning, [Line(self.worker, 10), Line(self.crm, 1)], pricelist=self.eur_20, commission=102),
            Spec(self.learning, [Line(self.worker, 20), Line(self.crm, 1)], pricelist=self.eur_20, commission=152),

            # learning: USD
            Spec(self.learning, [Line(self.worker, 10), Line(self.crm, 1)], pricelist=self.usd_8, commission=102),
            Spec(self.learning, [Line(self.worker, 20), Line(self.crm, 1)], pricelist=self.usd_8, commission=182),

            # ready: EUR
            Spec(self.ready, [Line(self.worker, 1), Line(self.crm, 1)], pricelist=self.eur_20, commission=102),
            Spec(self.ready, [Line(self.worker, 2), Line(self.crm, 1)], pricelist=self.eur_20, commission=152),

            # ready: USD
            Spec(self.ready, [Line(self.worker, 1), Line(self.crm, 1)], pricelist=self.usd_8, commission=102),
            Spec(self.ready, [Line(self.worker, 2), Line(self.crm, 1)], pricelist=self.usd_8, commission=182),

            # silver: EUR
            Spec(self.silver, [Line(self.worker, 1), Line(self.crm, 1)], pricelist=self.eur_20, commission=103),
            Spec(self.silver, [Line(self.worker, 2), Line(self.crm, 1)], pricelist=self.eur_20, commission=153),

            # silver: USD
            Spec(self.silver, [Line(self.worker, 1), Line(self.crm, 1)], pricelist=self.usd_8, commission=103),
            Spec(self.silver, [Line(self.worker, 2), Line(self.crm, 1)], pricelist=self.usd_8, commission=183),

            # gold: EUR
            Spec(self.gold, [Line(self.worker, 1), Line(self.crm, 1)], pricelist=self.eur_20, commission=104),
            Spec(self.gold, [Line(self.worker, 2), Line(self.crm, 1)], pricelist=self.eur_20, commission=154),

            # gold: USD
            Spec(self.gold, [Line(self.worker, 1), Line(self.crm, 1)], pricelist=self.usd_8, commission=104),
            Spec(self.gold, [Line(self.worker, 2), Line(self.crm, 1)], pricelist=self.usd_8, commission=184),
        ]

        for spec in specs:
            inv = self.purchase(spec)
            po = inv.commission_po_line_id.order_id
            comm = inv.commission_po_line_id.price_subtotal
            self.assertEqual(po.partner_id, self.referrer, '%s - %s: referrer != vendor' % (spec.grade.name, spec.pricelist.name))
            self.assertEqual(comm, spec.commission, '%s - %s: commission != expected' % (spec.grade.name, spec.pricelist.name))

        # global checks
        purchase_orders = self.env['purchase.order'].search([('partner_id', '=', self.referrer.id)])

        with self.subTest('Multiple SO should result in a single PO, with 1 line for each SO'):
            self.assertEqual(len(purchase_orders), 2, 'There should be 1 PO for each currency')

        po_eur = purchase_orders.filtered(lambda p: p.currency_id == self.env.ref('base.EUR'))
        with self.subTest('PO EUR'):
            self.assertEqual(len(po_eur.order_line), 8, 'Expected 8 purchase order lines')
            self.assertEqual(po_eur.amount_untaxed, 1022, 'PO EUR: total amount is wrong')

        po_usd = purchase_orders.filtered(lambda p: p.currency_id == self.env.ref('base.USD'))
        with self.subTest('PO USD'):
            self.assertEqual(len(po_usd.order_line), 8, 'Expected 8 purchase order lines')
            self.assertEqual(po_usd.amount_untaxed, 1142, 'PO USD: total amount is wrong')

    def test_partial_payments(self):
        """The PO should not be created unless the invoice is fully paid"""
        self.referrer.grade_id = self.gold.id
        self.referrer._onchange_grade_id()

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer

        with form.order_line.new() as line:
            line.name = self.crm.name
            line.product_id = self.crm
            line.product_uom_qty = 1

        so = form.save()
        so.action_confirm()

        inv = so._create_invoices()
        inv.post()

        # pay 10 out of 20
        payment_register = Form(self.env['account.payment'].with_context(active_model='account.move', active_ids=inv.ids))
        payment_register.payment_date = fields.Date.today()
        payment_register.journal_id = self.bank_journal
        payment_register.payment_method_id = self.env.ref('account.account_payment_method_manual_in')
        payment_register.amount = 10
        payment = payment_register.save()
        payment.post()

        self.assertEqual(inv.invoice_payment_state, 'not_paid')
        self.assertEqual(inv.amount_residual - inv.amount_tax, 10, 'Remaining untaxed amount to be paid: 10')
        self.assertFalse(inv.commission_po_line_id, 'Partially paid invoice should not create any PO')

    def test_refund(self):
        """A refund should add a negative line to the PO"""
        inv = self.purchase(Spec(self.gold, [Line(self.crm, 1)]))

        # refund
        ctx = {'active_model': 'account.move', 'active_ids': [inv.id]}
        move_reversal = self.env['account.move.reversal'].with_user(self.salesman).with_context(ctx).create({
            'date': fields.Date.today(),
            'reason': '...',
            'refund_method': 'refund',
        })
        reversal = move_reversal.reverse_moves()
        reverse_move = self.env['account.move'].browse(reversal['res_id'])
        reverse_move.post()
        self._pay_invoice(reverse_move)
        self.assertEqual(reverse_move.referrer_id, inv.referrer_id, 'Referrer should have been forwarded to credit note')
        self.assertEqual(reverse_move.commission_po_line_id, inv.commission_po_line_id)

        # check purchase order
        po = inv.commission_po_line_id.order_id
        self.assertEqual(len(po.order_line), 2, 'There should be two order lines when refunded')
        self.assertEqual(po.amount_total, 0, 'The total on the purchase order should be 0')
        self.assertEqual(po.order_line.mapped('price_subtotal'), [4, -4], 'The prices on the lines should be of 4 and -4')

    def test_group_before_capping(self):
        """The sum of commissions should be grouped by rules then capped, in that specific order."""
        self.learning_plan.commission_rule_ids.write({'is_capped': True, 'max_commission': 150})

        spec = Spec(self.learning, [Line(self.crm, 50), Line(self.invoicing, 50)], pricelist=self.eur_20, commission=150)
        inv = self.purchase(spec)

        po = inv.commission_po_line_id.order_id
        self.assertEqual(po.partner_id, self.referrer, 'Referrer != vendor')
        self.assertEqual(inv.commission_po_line_id.price_subtotal, spec.commission, 'Commission is wrong')
        self.assertEqual(len(po.order_line), 1, 'Expected 1 purchase order line')
