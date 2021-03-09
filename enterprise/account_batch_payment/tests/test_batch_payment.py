# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo.addons.account.tests.account_test_classes import AccountingTestCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestBatchPayment(AccountingTestCase):

    def setUp(self):
        super(TestBatchPayment, self).setUp()

        # Get some records
        self.customers = self.env['res.partner'].search([])
        self.batch_deposit = self.env.ref('account_batch_payment.account_payment_method_batch_deposit')

        # Create a bank journal
        journal_account = self.env['account.account'].create({
            'code': 'BNKT',
            'name': 'Bank Test',
            'user_type_id': self.ref('account.data_account_type_liquidity'),
        })
        self.journal = self.env['account.journal'].create({
            'name': 'Bank Test',
            'code': 'BNKT',
            'type': 'bank',
            'default_debit_account_id': journal_account.id,
            'default_credit_account_id': journal_account.id,
            'company_id': self.env.ref('base.main_company').id
        })

        # Create some payments
        self.payments = [
            self.createPayment(self.customers[0], 100),
            self.createPayment(self.customers[1], 200),
            self.createPayment(self.customers[2], 500),
        ]

    def createPayment(self, partner, amount):
        """ Create a batch deposit payment """
        return self.env['account.payment'].create({
            'journal_id': self.journal.id,
            'payment_method_id': self.batch_deposit.id,
            'payment_type': 'inbound',
            'payment_date': time.strftime('%Y') + '-07-15',
            'amount': amount,
            'partner_id': partner.id,
            'partner_type': 'customer',
        })

    def test_BatchLifeCycle(self):
        # Create and "print" a batch payment
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.journal.id,
            'payment_ids': [(4, payment.id, None) for payment in self.payments],
            'payment_method_id': self.batch_deposit.id,
        })
        batch.validate_batch()
        batch.print_batch_payment()
        self.assertTrue(all(payment.state == 'sent' for payment in self.payments))
        self.assertTrue(batch.state == 'sent')
        # Create a bank statement
        bank_statement = self.env['account.bank.statement'].create({
            'name': 'test deposit life cycle',
            'balance_start': 0.0,
            'balance_end_real': 800.0,
            'date': time.strftime('%Y') + '-08-01',
            'journal_id': self.journal.id,
            'company_id': self.env.ref('base.main_company').id,
        })
        bank_statement_line = self.env['account.bank.statement.line'].create({
            'amount': 800,
            'date': time.strftime('%Y') + '-07-18',
            'name': 'DEPOSIT',
            'statement_id': bank_statement.id,
        })
        # Simulate the process of reconciling the statement line using the batch deposit
        deposits_reconciliation_data = self.env['account.reconciliation.widget'].get_batch_payments_data(bank_statement.ids)
        self.assertTrue(len(deposits_reconciliation_data), 1)
        self.assertTrue(deposits_reconciliation_data[0]['id'], batch.id)
        deposit_reconciliation_lines = self.env['account.reconciliation.widget'].get_move_lines_by_batch_payment(bank_statement_line.id, batch.id)
        self.assertTrue(len(deposit_reconciliation_lines), 3)
        move_line_ids = [line['id'] for line in deposit_reconciliation_lines]
        self.env['account.reconciliation.widget'].process_bank_statement_line(bank_statement_line.ids, [{"payment_aml_ids": move_line_ids}])
        self.assertTrue(all(payment.state == 'reconciled' for payment in self.payments))
        self.assertTrue(batch.state == 'reconciled')

    def test_zero_amount_payment(self):
        zero_payment = self.createPayment(self.customers[0], 0)
        batch_vals = {
            'journal_id': self.journal.id,
            'payment_ids': [(4, zero_payment.id, None)],
            'payment_method_id': self.batch_deposit.id,
        }
        self.assertRaises(ValidationError, self.env['account.batch.payment'].create, batch_vals)
