# -*- coding: utf-8 -*-
import datetime

from odoo import fields
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


class TestSubscriptionSEPA(TestSubscriptionCommon):

    def setUp(self):
        super(TestSubscriptionSEPA, self).setUp()

        self.sepa = self.env.ref('payment.payment_acquirer_sepa_direct_debit')
        bank_account = self.env['res.partner.bank'].create({
            'acc_number': 'NL91 ABNA 0417 1643 00',
            'partner_id': self.env.company.partner_id.id,
            'bank_id': self.env.ref('base.bank_ing').id,
        })
        journal = self.env['account.journal'].create({
            'name': 'Bank SEPA',
            'type': 'bank',
            'code': 'BNKSEPA',
            'post_at': 'bank_rec',
            'inbound_payment_method_ids': [(4, self.env.ref('account_sepa_direct_debit.payment_method_sdd').id)],
            'bank_account_id': bank_account.id,
        })
        self.sepa.write({'journal_id': journal.id})

        self.partner_bank = self.env['res.partner.bank'].create({
            'acc_number': 'BE17412614919710',
            'partner_id': self.user_portal.partner_id.id,
            'company_id': self.env.company.id,
        })

        self.mandate = self.env['sdd.mandate'].create({
            'partner_id': self.user_portal.partner_id.id,
            'company_id': self.env.company.id,
            'partner_bank_id': self.partner_bank.id,
            'start_date': fields.date.today(),
            'payment_journal_id': self.sepa.journal_id.id,
            'verified': True,
            'state': 'active',
        })

        self.payment_token = self.env['payment.token'].create({
            'name': 'BE17412614919710',
            'partner_id': self.user_portal.partner_id.id,
            'acquirer_id': self.sepa.id,
            'acquirer_ref': self.mandate.name,
            'sdd_mandate_id': self.mandate.id,
        })

    def test_01_recurring_invoice(self):
        from mock import patch

        self.account_type_receivable = self.env['account.account.type'].create({
            'name': 'receivable',
            'type': 'receivable',
            'internal_group': 'asset',
        })
        self.account_receivable = self.env['account.account'].create({
            'name': 'Ian Anderson',
            'code': 'IA',
            'user_type_id': self.account_type_receivable.id,
            'company_id': self.env.company.id,
            'reconcile': True,
        })
        self.user_portal.partner_id.write({
            'property_account_receivable_id': self.account_receivable.id,
            'property_account_payable_id': self.account_receivable.id,
        })
        self.subscription_tmpl.write({'invoice_mail_template_id': self.env.ref('sale_subscription.mail_template_subscription_invoice').id})
        self.subscription.write({
            'partner_id': self.user_portal.partner_id.id,
            'recurring_next_date': fields.Date.to_string(datetime.date.today()),
            'template_id': self.subscription_tmpl.id,
            'company_id': self.env.company.id,
            'payment_token_id': self.payment_token.id,
            'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': 50, 'uom_id': self.product.uom_id.id})],
            'stage_id': self.ref('sale_subscription.sale_subscription_stage_in_progress'),
        })

        for payment_mode in ['validate_send_payment', 'success_payment']:
            self.send_success_count = 0
            self.subscription_tmpl.write({'payment_mode': payment_mode})

            def assertEqual(got, want, msg):
                self.assertEqual(got, want, '%s: %s' % (payment_mode, msg))

            sub = self.subscription.copy()
            with patch('odoo.addons.sale_subscription.models.sale_subscription.SaleSubscription.send_success_mail', wraps=self._mock_send_success_mail):
                sub.with_context(auto_commit=False)._recurring_create_invoice(automatic=True)

                # check success mail is not sent yet
                assertEqual(self.send_success_count, 0, 'success mail should not be sent before reconciliation')

                # check invoice amount and taxes
                invoice_id = sub.action_subscription_invoice()['res_id']
                invoice = self.env['account.move'].browse(invoice_id)
                recurring_total_with_taxes = sub.recurring_total + (sub.recurring_total * (self.tax_10.amount / 100.0))
                assertEqual(invoice.amount_total, recurring_total_with_taxes, 'subscription total amount should be tax included')

                # check transaction state
                tx = invoice.mapped('transaction_ids')
                payment = tx.payment_id
                assertEqual(len(tx), 1, 'a single transaction should be created')
                assertEqual(tx.state, 'pending', 'transaction should be pending')
                assertEqual(payment.state, 'posted', 'payment should be posted')
                assertEqual(invoice.invoice_payment_state, 'in_payment', 'invoice should be in_payment')
                assertEqual(invoice.state, 'posted', 'move should be posted')

                # reconcile the payment
                bank_journal = payment.journal_id
                bank_stmt = self.env['account.bank.statement'].create({
                    'journal_id': bank_journal.id,
                    'date': payment.payment_date,
                    'name': payment.name,
                })
                bank_stmt_line = self.env['account.bank.statement.line'].create({
                    'statement_id': bank_stmt.id,
                    'partner_id': self.user_portal.partner_id.id,
                    'amount': payment.amount,
                    'date': payment.payment_date,
                    'name': payment.name,
                })
                move_line = payment.move_line_ids.filtered(lambda aml: aml.account_id in bank_journal.default_debit_account_id + bank_journal.default_credit_account_id)
                bank_stmt_line.process_reconciliation(payment_aml_rec=move_line)

                # check success mail is sent
                assertEqual(self.send_success_count, 1, 'success mail should have been sent, now that the payment is reconciled')

                # check post-reconciliation states
                assertEqual(payment.state, 'reconciled', 'payment should be reconciled')
                assertEqual(tx.state, 'done', 'transaction should be done')
                assertEqual(invoice.state, 'posted', 'invoice should be posted')
                assertEqual(invoice.invoice_payment_state, 'paid', 'invoice should be paid')

    def _mock_send_success_mail(self, tx, invoice):
        self.send_success_count += 1
