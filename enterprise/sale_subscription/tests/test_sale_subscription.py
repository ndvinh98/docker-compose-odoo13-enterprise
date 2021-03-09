# -*- coding: utf-8 -*-
import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon
from odoo.tests import Form
from odoo.tools import mute_logger
from odoo import fields


class TestSubscription(TestSubscriptionCommon):

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_01_template(self):
        """ Test behaviour of on_change_template """
        Subscription = self.env['sale.subscription']

        # on_change_template on existing record (present in the db)
        self.subscription.template_id = self.subscription_tmpl
        self.subscription.on_change_template()
        self.assertTrue(self.subscription.description, 'sale_subscription: description not copied on existing sale.subscription record')

        # on_change_template on cached record (NOT present in the db)
        temp = Subscription.new({'name': 'CachedSubscription',
                                 'partner_id': self.user_portal.partner_id.id})
        temp.update({'template_id': self.subscription_tmpl.id})
        temp.on_change_template()
        self.assertTrue(temp.description, 'sale_subscription: description not copied on new cached sale.subscription record')

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_02_sale_order(self):
        """ Test sales order line copying for recurring products on confirm"""
        self.sale_order.action_confirm()
        self.assertTrue(len(self.subscription.recurring_invoice_line_ids.ids) == 1, 'sale_subscription: recurring_invoice_line_ids not created when confirming sale_order with recurring_product')
        self.assertEqual(self.sale_order.subscription_management, 'upsell', 'sale_subscription: so should be set to "upsell" if not specified otherwise')

    def test_03_auto_close(self):
        """Ensure a 15 days old 'online payment' subscription gets closed if no token is set."""
        self.subscription_tmpl.payment_mode = 'success_payment'
        self.subscription.write({
            'recurring_next_date': fields.Date.to_string(datetime.date.today() - relativedelta(days=17)),
            'recurring_total': 42,
            'template_id': self.subscription_tmpl.id,
        })
        self.subscription.with_context(auto_commit=False)._recurring_create_invoice(automatic=True)
        self.assertEqual(self.subscription.in_progress, False, 'website_contrect: subscription with online payment and no payment method set should get closed after 15 days')

    # Mocking for 'test_auto_payment_with_token'
    # Necessary to have a valid and done transaction when the cron on subscription passes through
    def _mock_subscription_do_payment(self, payment_method, invoice, two_steps_sec=True):
        tx_obj = self.env['payment.transaction']
        reference = "CONTRACT-%s-%s" % (self.id, datetime.datetime.now().strftime('%y%m%d_%H%M%S'))
        values = {
            'amount': invoice.amount_total,
            'acquirer_id': self.acquirer.id,
            'type': 'server2server',
            'currency_id': invoice.currency_id.id,
            'reference': reference,
            'payment_token_id': payment_method.id,
            'partner_id': invoice.partner_id.id,
            'partner_country_id': invoice.partner_id.country_id.id,
            'invoice_ids': [(6, 0, [invoice.id])],
            'state': 'done',
        }
        tx = tx_obj.create(values)
        return tx

    # Mocking for 'test_auto_payment_with_token'
    # Otherwise the whole sending mail process will be triggered
    # And we are not here to test that flow, and it is a heavy one
    def _mock_subscription_send_success_mail(self, tx, invoice):
        self.mock_send_success_count += 1
        return 666

    # Mocking for 'test_auto_payment_with_token'
    # Avoid account_id is False when creating the invoice
    def _mock_prepare_invoice_data(self):
        invoice = self.original_prepare_invoice_data()
        invoice['invoice_partner_bank_id'] = False
        return invoice

    # Mocking for 'test_auto_payment_with_token'
    # Avoid account_id is False when creating the invoice
    def _mock_prepare_invoice_line(self, line, fiscal_position, date_start=False, date_stop=False):
        line_values = self.original_prepare_invoice_line(line, fiscal_position, date_start, date_stop)
        return line_values

    def test_04_auto_payment_with_token(self):
        from mock import patch

        self.company = self.env.company

        self.account_type_receivable = self.env['account.account.type'].create({
            'name': 'receivable',
            'type': 'receivable',
            'internal_group': 'asset',
        })

        self.account_receivable = self.env['account.account'].create(
            {'name': 'Ian Anderson',
             'code': 'IA',
             'user_type_id': self.account_type_receivable.id,
             'company_id': self.company.id,
             'reconcile': True})

        self.account_type_sale = self.env['account.account.type'].create({
            'name': 'income',
            'type': 'other',
            'internal_group': 'income',
        })
        self.account_sale = self.env['account.account'].create(
            {'name': 'Product Sales ',
             'code': 'S200000',
             'user_type_id': self.account_type_sale.id,
             'company_id': self.company.id,
             'reconcile': False})

        self.sale_journal = self.env['account.journal'].create(
            {'name': 'reflets.info',
             'code': 'ref',
             'type': 'sale',
             'company_id': self.company.id,
             'sequence_id': self.env['ir.sequence'].search([], limit=1).id,
             'default_credit_account_id': self.account_sale.id,
             'default_debit_account_id': self.account_sale.id})

        self.partner = self.env['res.partner'].create(
            {'name': 'Stevie Nicks',
             'email': 'sti@fleetwood.mac',
             'property_account_receivable_id': self.account_receivable.id,
             'property_account_payable_id': self.account_receivable.id,
             'company_id': self.company.id})

        self.acquirer = self.env['payment.acquirer'].create(
            {'name': 'The Wire',
             'provider': 'transfer',
             'company_id': self.company.id,
             'state': 'test',
             'view_template_id': self.env['ir.ui.view'].search([('type', '=', 'qweb')], limit=1).id})

        self.payment_method = self.env['payment.token'].create(
            {'name': 'Jimmy McNulty',
             'partner_id': self.partner.id,
             'acquirer_id': self.acquirer.id,
             'acquirer_ref': 'Omar Little'})

        self.original_prepare_invoice_data = self.subscription._prepare_invoice_data
        self.original_prepare_invoice_line = self.subscription._prepare_invoice_line

        patchers = [
            patch('odoo.addons.sale_subscription.models.sale_subscription.SaleSubscription._prepare_invoice_line', wraps=self._mock_prepare_invoice_line, create=True),
            patch('odoo.addons.sale_subscription.models.sale_subscription.SaleSubscription._prepare_invoice_data', wraps=self._mock_prepare_invoice_data, create=True),
            patch('odoo.addons.sale_subscription.models.sale_subscription.SaleSubscription._do_payment', wraps=self._mock_subscription_do_payment, create=True),
            patch('odoo.addons.sale_subscription.models.sale_subscription.SaleSubscription.send_success_mail', wraps=self._mock_subscription_send_success_mail, create=True),
        ]

        for patcher in patchers:
            patcher.start()

        self.subscription_tmpl.payment_mode = 'success_payment'

        self.subscription.write({
            'partner_id': self.partner.id,
            'recurring_next_date': fields.Date.to_string(datetime.date.today()),
            'template_id': self.subscription_tmpl.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_method.id,
            'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': 50, 'uom_id': self.product.uom_id.id})],
            'stage_id': self.ref('sale_subscription.sale_subscription_stage_in_progress'),
        })
        self.mock_send_success_count = 0
        self.subscription.with_context(auto_commit=False)._recurring_create_invoice(automatic=True)
        self.assertEqual(self.mock_send_success_count, 1, 'a mail to the invoice recipient should have been sent')
        self.assertEqual(self.subscription.in_progress, True, 'subscription with online payment and a payment method set should stay opened when transaction succeeds')

        invoice_id = self.subscription.action_subscription_invoice()['res_id']
        invoice = self.env['account.move'].browse(invoice_id)
        recurring_total_with_taxes = self.subscription.recurring_total + (self.subscription.recurring_total * (self.tax_10.amount / 100.0))
        self.assertEqual(invoice.amount_total, recurring_total_with_taxes, 'website_subscription: the total of the recurring invoice created should be the subscription recurring total + the products taxes')
        self.assertTrue(all(line.tax_ids.ids == self.tax_10.ids for line in invoice.invoice_line_ids), 'website_subscription: All lines of the recurring invoice created should have the percent tax set on the subscription products')
        self.assertTrue(all(tax_line.tax_line_id == self.tax_10 for tax_line in invoice.line_ids.filtered('tax_line_id')), 'The invoice tax lines should be set and should all use the tax set on the subscription products')

        for patcher in patchers:
            patcher.stop()

    def test_05_sub_creation(self):
        """ Test multiple subscription creation from single SO"""
        # Test subscription creation on SO confirm
        self.sale_order_2.action_confirm()
        self.assertEqual(len(self.sale_order_2.order_line.mapped('subscription_id')), 1, 'sale_subscription: subscription should be created on SO confirmation')
        self.assertEqual(self.sale_order_2.subscription_management, 'create', 'sale_subscription: subscription creation should set the SO to "create"')

        # Two product with different subscription template
        self.sale_order_3.action_confirm()
        self.assertEqual(len(self.sale_order_3.order_line.mapped('subscription_id')), 2, 'sale_subscription: Two different subscription should be created on SO confirmation')
        self.assertEqual(self.sale_order_3.subscription_management, 'create', 'sale_subscription: subscription creation should set the SO to "create"')

        # Two product with same subscription template
        self.sale_order_4.action_confirm()
        self.assertEqual(len(self.sale_order_4.order_line.mapped('subscription_id')), 1, 'sale_subscription: One subscription should be created on SO confirmation')
        self.assertEqual(self.sale_order_4.subscription_management, 'create', 'sale_subscription: subscription creation should set the SO to "create"')

        today = fields.Date.context_today(self.env.user)
        self.sale_order_5.action_confirm()
        self.assertEqual(self.sale_order_5.order_line.subscription_id.date, today + relativedelta(months=+1), 'sale_subscription: subscription creation should set the end date to : today + 1 month')

    @mute_logger('odoo.models.unlink')
    def test_06_renewal(self):
        """ Test subscription renewal """
        res = self.subscription.prepare_renewal_order()
        renewal_so_id = res['res_id']
        renewal_so = self.env['sale.order'].browse(renewal_so_id)
        so_line_vals = {
            'name': self.product.name,
            'order_id': renewal_so_id,
            'product_id': self.product.id,
            'product_uom_qty': 2,
            'product_uom': self.product.uom_id.id,
            'price_unit': self.product.list_price}
        new_line = self.env['sale.order.line'].with_context(dbo=True).create(so_line_vals)
        self.assertEqual(new_line.subscription_id, self.subscription, 'sale_subscription: SO lines added to renewal orders manually should have the correct subscription set on them')
        self.assertEqual(renewal_so.origin, self.subscription.code, 'sale_subscription: renewal order must have the "source document" set to the subscription code')
        self.assertTrue(renewal_so.subscription_management == 'renew', 'sale_subscription: renewal quotation generation is wrong')
        self.subscription.write({'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': 50, 'uom_id': self.product.uom_id.id})]})
        renewal_so.write({'order_line': [(0, 0, {'product_id': self.product.id, 'subscription_id': self.subscription.id, 'name': 'TestRenewalLine', 'product_uom': self.product.uom_id.id})]})
        renewal_so.action_confirm()
        lines = [line.name for line in self.subscription.mapped('recurring_invoice_line_ids')]
        self.assertTrue('TestRecurringLine' not in lines, 'sale_subscription: old line still present after renewal quotation confirmation')
        self.assertTrue('TestRenewalLine' in lines, 'sale_subscription: new line not present after renewal quotation confirmation')
        self.assertEqual(renewal_so.subscription_management, 'renew', 'sale_subscription: so should be set to "renew" in the renewal process')

    def test_07_upsell_via_so(self):
        """Test the upsell flow using an intermediary upsell quote."""
        wiz = self.env['sale.subscription.wizard'].create({
            'subscription_id': self.subscription.id,
            'option_lines': [(0, False, {'product_id': self.product.id, 'name': self.product.name, 'uom_id': self.product.uom_id.id})]
        })
        upsell_so_id = wiz.create_sale_order()['res_id']
        upsell_so = self.env['sale.order'].browse(upsell_so_id)
        # add line to quote manually, it must be taken into account in the subscription after validation
        so_line_vals = {
            'name': self.product2.name,
            'order_id': upsell_so_id,
            'product_id': self.product2.id,
            'product_uom_qty': 2,
            'product_uom': self.product2.uom_id.id,
            'price_unit': self.product2.list_price}
        new_line = self.env['sale.order.line'].create(so_line_vals)
        self.assertEqual(self.subscription, new_line.subscription_id,
                         '''sale_subscription: upsell line added to quote after '''
                         '''creation but before validation must be automatically '''
                         '''linked to correct subscription''')
        upsell_so.action_confirm()
        self.assertEqual(len(self.subscription.recurring_invoice_line_ids), 2)

    def test_08_recurring_revenue(self):
        """Test computation of recurring revenue"""
        # Initial subscription is $100/y
        self.subscription_tmpl.recurring_rule_type = 'yearly'
        y_price = 100
        self.sale_order.action_confirm()
        subscription = self.sale_order.order_line.mapped('subscription_id')
        self.assertAlmostEqual(subscription.recurring_total, y_price, msg="unexpected price after setup")
        self.assertAlmostEqual(subscription.recurring_monthly, y_price / 12.0, msg="unexpected MRR")
        # Change interval to 3 weeks
        subscription.template_id.recurring_rule_type = 'weekly'
        subscription.template_id.recurring_interval = 3
        self.assertAlmostEqual(subscription.recurring_total, y_price, msg='total should not change when interval changes')
        self.assertAlmostEqual(subscription.recurring_monthly, y_price * (30 / 7.0) / 3, msg='unexpected MRR')

    def test_09_analytic_account(self):
        """Analytic accounting flow."""
        # analytic account is copied on order confirmation
        self.sale_order_3.analytic_account_id = self.account_1
        self.sale_order_3.action_confirm()
        subscriptions = self.sale_order_3.order_line.mapped('subscription_id')
        for subscription in subscriptions:
            self.assertEqual(self.sale_order_3.analytic_account_id, subscription.analytic_account_id)
            inv = subscription._recurring_create_invoice()
            # invoice lines have the correct analytic account
            self.assertEqual(inv.invoice_line_ids[0].analytic_account_id, subscription.analytic_account_id)
            subscription.analytic_account_id = self.account_2
            # even if changed after the fact
            inv = subscription._recurring_create_invoice()
            self.assertEqual(inv.invoice_line_ids[0].analytic_account_id, subscription.analytic_account_id)

    def test_10_take_snapshot(self):
        Snapshot = self.env['sale.subscription.snapshot']
        before_count = Snapshot.search_count([('subscription_id', '=', self.subscription.id)])
        self.subscription._take_snapshot(datetime.date.today() - relativedelta(weeks=1))
        after_count = Snapshot.search_count([('subscription_id', '=', self.subscription.id)])
        self.assertEqual(after_count, before_count + 1)

    def test_11_compute_kpi(self):
        self.subscription.template_id.write({
            'good_health_domain': "[('recurring_monthly', '>=', 120.0)]",
            'bad_health_domain': "[('recurring_monthly', '<=', 80.0)]",
        })
        self.subscription.recurring_monthly = 80.0
        self.subscription._take_snapshot(datetime.date.today() - relativedelta(weeks=16))
        self.subscription._compute_kpi()
        sub = self.subscription.browse(self.subscription.id)
        self.assertEqual(sub.health, 'bad')
        self.subscription.recurring_monthly = 100.0
        self.subscription._take_snapshot(datetime.date.today() - relativedelta(weeks=6))
        self.subscription.recurring_monthly = 100.0
        self.subscription._take_snapshot(datetime.date.today() - relativedelta(weeks=4))
        self.subscription.recurring_monthly = 120.0
        self.subscription._take_snapshot(datetime.date.today() - relativedelta(weeks=2))
        self.subscription._compute_kpi()
        self.assertEqual(self.subscription.kpi_1month_mrr_delta, 20.0)
        self.assertEqual(self.subscription.kpi_1month_mrr_percentage, 0.2)
        self.assertEqual(self.subscription.kpi_3months_mrr_delta, 40.0)
        self.assertEqual(self.subscription.kpi_3months_mrr_percentage, 0.5)
        self.assertEqual(self.subscription.health, 'done')

    def test_12_cron_update_kpi(self):
        Snapshot = self.env['sale.subscription.snapshot']
        subscriptions_count = self.env['sale.subscription'].search_count([('in_progress', '=', True)])
        before_count = Snapshot.search_count([])
        self.env['sale.subscription']._cron_update_kpi()
        after_count = Snapshot.search_count([])
        self.assertEqual(after_count, before_count + subscriptions_count)

    def test_13_onchange_date_start(self):
        recurring_bound_tmpl = self.env['sale.subscription.template'].create({
            'name': 'Recurring Bound Template',
            'recurring_rule_boundary': 'limited',
        })
        sub_form = Form(self.env['sale.subscription'])
        sub_form.partner_id = self.user_portal.partner_id
        sub_form.template_id = recurring_bound_tmpl
        sub = sub_form.save()
        self.assertEqual(sub.template_id.recurring_rule_boundary, 'limited')
        self.assertIsInstance(sub.date, datetime.date)

    @mute_logger('odoo.addons.mail.models.mail_mail', 'odoo.models.unlink')
    def test_14_default_salesperson(self):
        partner = self.env['res.partner'].create({'name': 'Tony Stark'})
        sub_form = Form(self.env['sale.subscription'])
        sub_form.template_id = self.subscription_tmpl
        sub_form.partner_id = partner
        sub = sub_form.save()
        self.assertEqual(sub.user_id, self.env.user)

        partner.user_id = self.user_portal
        sub_form = Form(self.env['sale.subscription'])
        sub_form.template_id = self.subscription_tmpl
        sub_form.partner_id = partner
        sub = sub_form.save()
        self.assertEqual(sub.user_id, self.user_portal)

    def test_15_next_invoice_date_last_date_of_month(self):
        """ This testcase will check the next invoice dates for monthly subscription. """
        self.subscription_tmpl.recurring_interval = 1
        # Created subscription with `date_start` set to last day of December and `recurring_next_date` as last day of January.
        sub = self.subscription.copy({'date_start': '2017-12-31', 'recurring_next_date': '2018-01-31'})
        self.assertEqual(sub.recurring_invoice_day, 31, 'Next Invoice Day should be 31.')
        # Since the monthly subscription starts on the 31st day of December, the next invoice should be generated on the same day of next month
        # except for the months which does not have the same day, in such cases, it should be generated on last day of that particular month
        sub.recurring_invoice()
        self.assertEqual(sub.recurring_next_date, datetime.date(2018, 2, 28), '`Date of Next Invoice` should be the last day of February 2018.')
        sub.recurring_invoice()
        self.assertEqual(sub.recurring_next_date, datetime.date(2018, 3, 31), '`Date of Next Invoice` should be the last day of March 2018.')
        sub.recurring_invoice()
        self.assertEqual(sub.recurring_next_date, datetime.date(2018, 4, 30), '`Date of Next Invoice` should be the last day of April 2018.')

    def test_16_changed_next_invoice_date(self):
        """This testcase will check next invoice dates if user change next invoice date manually"""
        self.subscription_tmpl.recurring_interval = 1
        # Created subscription with `date_start` and `recurring_next_date` to 5th of February and March respectively.
        sub = self.subscription.copy({'date_start': '2018-02-05', 'recurring_next_date': '2018-03-05'})
        # Since the monthly subscription's `recurring_next_date` is set to 5th March(ie. it is not the last day of month), `recurring_next_date` should be set to the same day of next month
        sub.recurring_invoice()
        self.assertEqual(sub.recurring_next_date, datetime.date(2018, 4, 5), '`Date of Next Invoice` should be 5th April 2018.')
        # Manually changing `recurring_next_date` to the last day of April 2018.
        sub.recurring_next_date = '2018-04-30'
        # `recurring_invoice_day` should be set to 30 as `recurring_next_date` was modified manually(and not by cron)
        self.assertEqual(sub.recurring_invoice_day, 30, 'Next Invoice Day should be 30.')
        # We have changed next invoice date to 30th of April, the next invoice should be generated on 30th of next month
        sub.recurring_invoice()
        self.assertEqual(sub.recurring_next_date, datetime.date(2018, 5, 30), '`Date of Next Invoice` should be 30th May 2018.')
        sub.recurring_invoice()
        self.assertEqual(sub.recurring_next_date, datetime.date(2018, 6, 30), '`Date of Next Invoice` should be 30th June 2018.')
