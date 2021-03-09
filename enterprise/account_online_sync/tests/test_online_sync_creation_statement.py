# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account.tests.account_test_classes import AccountingTestCase
from odoo.tests import tagged
from odoo import fields


@tagged('post_install','-at_install')
class TestSynchStatementCreation(AccountingTestCase):
    def setUp(self):
        super(TestSynchStatementCreation, self).setUp()
        self.bnk_stmt = self.env['account.bank.statement']
        # some users
        group_account_adviser = self.env.ref('account.group_account_manager')
        self.adviser = self.env['res.users'].create({
            'name': 'Alfred Glasses',
            'login': 'adviser',
            'email': 'a.g@example.com',
            'signature': '--\nAlfred',
            'groups_id': [(6, 0, [group_account_adviser.id])]
        })

        # Create an account.online.provider and account.online.journal and associate to journal bank
        self.bank_journal = self.env['account.journal'].create({'name': 'Bank_Online', 'type': 'bank', 'code': 'BNKonl', 'currency_id': self.env.ref('base.EUR').id})
        self.provider_account = self.env['account.online.provider'].create({'name': 'Test Bank'})
        self.online_account = self.env['account.online.journal'].create({
            'name': 'MyBankAccount',
            'account_online_provider_id': self.provider_account.id,
            'journal_ids': [(6, 0, [self.bank_journal.id])]
        })
        self.transaction_id = 1
        self.account = self.env['account.account'].create({
            'name': 'toto',
            'code': 'bidule',
            'user_type_id': self.env.ref('account.data_account_type_fixed_assets').id
        })

    def create_bank_statement_date(self, date):
        bank_statement_line_vals = {'name': 'test_line', 'date': date, 'amount': 50}
        bank_stmt = self.bnk_stmt.create({
            'date': fields.Date.from_string(date),
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, bank_statement_line_vals)],
            'balance_start': 0,
            'balance_end_real': 50,
        })
        return bank_stmt

    def delete_bank_statement(self, statement):
        statement.unlink()

    def create_transaction(self, date1, date2):
        tr1 = {
                'online_identifier': self.transaction_id,
                'date': fields.Date.from_string(date1),
                'name': 'transaction',
                'amount': 50,
                'end_amount': 1900,
            }
        tr2 = {
                'online_identifier': self.transaction_id + 1,
                'date': fields.Date.from_string(date2),
                'name': 'transaction2',
                'amount': 50,
                'end_amount': 1900,
            }
        self.transaction_id += 2
        return [tr1, tr2]

    def create_transaction_partner(self, partner_id=False, vendor_name=False, account_number=False):
        tr = {
            'online_identifier': self.transaction_id,
            'date': fields.Date.from_string('2016-01-10'),
            'name': 'transaction_p',
            'amount': 50,
            'end_amount': 50
        }
        if partner_id:
            tr['partner_id'] = partner_id
        if vendor_name:
            tr['online_partner_vendor_name'] = vendor_name
        if account_number:
            tr['online_partner_bank_account'] = account_number
        self.transaction_id += 1
        return [tr]

    def confirm_bank_statement(self, statement):
        
        statement.line_ids[0].process_reconciliation(new_aml_dicts=[{
            'credit': 50,
            'debit': 0,
            'name': 'toto',
            'account_id': self.account.id,
        }])
        statement.button_confirm_bank()
        return statement

    def test_creation_every_sync(self):
        self.create_bank_statement_date('2016-01-01')
        transactions = self.create_transaction('2016-01-01', '2016-01-01')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        # Verify that we have 2 bank statements and one with the two newly created transactions
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 2, 'Should have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[1].line_ids), 2, 'Newly created bank statement should have 2 lines')
        self.delete_bank_statement(created_bnk_stmt)

    def test_creation_every_day(self):
        self.bank_journal.write({'bank_statement_creation': 'day'})
        transactions = self.create_transaction('2016-01-01', '2016-01-01')
        # first synchronization, no previous bank statement
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should have created a single bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'bank statement should have 3 lines (2 added + opening entry)')
        self.assertEqual(created_bnk_stmt[0].balance_end_real, 1900, 'Newly bank statement balance end should be fetched from transaction')
        self.delete_bank_statement(created_bnk_stmt)
        # already have bank statement
        bank_stmt = self.create_bank_statement_date('2016-01-01')
        self.assertEqual(len(bank_stmt.line_ids), 1, 'Previous bank statement should have 1 line to start')
        # Add 2 transactions same day, both should be added to previous bank statement
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should not have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'Previous bank statement should now have 3 lines')
        # Add 1 transaction same day and 1 next day, the first should be on previous bank statement and latest in new bank stmt
        transactions = self.create_transaction('2016-01-01', '2016-01-02')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 2, 'Should have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 4, 'Previous bank statement should now have 4 lines')
        self.assertEqual(len(created_bnk_stmt[1].line_ids), 1, 'Newly bank statement should have 1 line')
        self.assertEqual(created_bnk_stmt[1].balance_end_real, 250, 'Newly bank statement balance end should be 250')
        self.assertEqual(created_bnk_stmt[1].balance_start, 200, 'Newly bank statement balance start should be 200')
        #remove bank statement
        self.delete_bank_statement(created_bnk_stmt)

    def test_creation_every_week(self):
        self.bank_journal.write({'bank_statement_creation': 'week'})
        transactions = self.create_transaction('2016-01-01', '2016-01-01')
        # first synchronization, no previous bank statement
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should have created a single bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'bank statement should have 3 lines (2 added + opening entry)')
        self.assertEqual(created_bnk_stmt[0].balance_end_real, 1900, 'Newly bank statement balance end should be fetched from transaction')
        self.delete_bank_statement(created_bnk_stmt)
        # already have bank statement
        bank_stmt = self.create_bank_statement_date('2016-01-01')
        self.assertEqual(len(bank_stmt.line_ids), 1, 'Previous bank statement should have 1 line to start')
        # Add 2 transactions same day, both should be added to previous bank statement
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should not have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'Previous bank statement should now have 3 lines')
        # Add 1 transaction in the week and 1 next week, the first should be on previous bank statement and latest in new bank stmt
        transactions = self.create_transaction('2016-01-03', '2016-01-07')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 2, 'Should have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 4, 'Previous bank statement should now have 4 lines')
        self.assertEqual(len(created_bnk_stmt[1].line_ids), 1, 'Newly bank statement should have 1 line')
        self.assertEqual(created_bnk_stmt[1].balance_end_real, 250, 'Newly bank statement balance end should be 250')
        self.assertEqual(created_bnk_stmt[1].balance_start, 200, 'Newly bank statement balance start should be 200')
        #remove bank statement
        self.delete_bank_statement(created_bnk_stmt)

    def test_creation_every_2weeks(self):
        self.bank_journal.write({'bank_statement_creation': 'bimonthly'})
        transactions = self.create_transaction('2016-01-01', '2016-01-01')
        # first synchronization, no previous bank statement
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should have created a single bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'bank statement should have 3 lines (2 added + opening entry)')
        self.assertEqual(created_bnk_stmt[0].balance_end_real, 1900, 'Newly bank statement balance end should be fetched from transaction')
        self.delete_bank_statement(created_bnk_stmt)
        # already have bank statement
        bank_stmt = self.create_bank_statement_date('2016-01-01')
        self.assertEqual(len(bank_stmt.line_ids), 1, 'Previous bank statement should have 1 line to start')
        # Add 2 transactions same half of month, both should be added to previous bank statement
        transactions = self.create_transaction('2016-01-01', '2016-01-15')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should not have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'Previous bank statement should now have 3 lines')
        # Add 1 transaction in the same half month and 1 next half, the first should be on previous bank statement and latest in new bank stmt
        transactions = self.create_transaction('2016-01-10', '2016-01-16')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 2, 'Should have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 4, 'Previous bank statement should now have 4 lines')
        self.assertEqual(len(created_bnk_stmt[1].line_ids), 1, 'Newly bank statement should have 1 line')
        self.assertEqual(created_bnk_stmt[1].balance_end_real, 250, 'Newly bank statement balance end should be 250')
        self.assertEqual(created_bnk_stmt[1].balance_start, 200, 'Newly bank statement balance start should be 200')
        #remove bank statement
        self.delete_bank_statement(created_bnk_stmt)

    def test_creation_every_month(self):
        self.bank_journal.write({'bank_statement_creation': 'month'})
        transactions = self.create_transaction('2016-01-01', '2016-01-01')
        # first synchronization, no previous bank statement
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should have created a single bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'bank statement should have 3 lines (2 added + opening entry)')
        self.assertEqual(created_bnk_stmt[0].balance_end_real, 1900, 'Newly bank statement balance end should be fetched from transaction')
        self.delete_bank_statement(created_bnk_stmt)
        # already have bank statement
        bank_stmt = self.create_bank_statement_date('2016-01-01')
        self.assertEqual(len(bank_stmt.line_ids), 1, 'Previous bank statement should have 1 line to start')
        # Add 2 transactions same month, both should be added to previous bank statement
        transactions = self.create_transaction('2016-01-15', '2016-01-31')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 1, 'Should not have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 3, 'Previous bank statement should now have 3 lines')
        # Add 1 transaction in the month and 1 next month, the first should be on previous bank statement and latest in new bank stmt
        transactions = self.create_transaction('2016-01-21', '2016-02-01')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id')
        self.assertEqual(len(created_bnk_stmt), 2, 'Should have created a new bank statement')
        self.assertEqual(len(created_bnk_stmt[0].line_ids), 4, 'Previous bank statement should now have 4 lines')
        self.assertEqual(len(created_bnk_stmt[1].line_ids), 1, 'Newly bank statement should have 1 line')
        self.assertEqual(created_bnk_stmt[1].balance_end_real, 250, 'Newly bank statement balance end should be 250')
        self.assertEqual(created_bnk_stmt[1].balance_start, 200, 'Newly bank statement balance start should be 200')
        #remove bank statement
        self.delete_bank_statement(created_bnk_stmt)

    def test_assign_partner_auto_bank_stmt(self):
        self.bank_journal.write({'bank_statement_creation': 'day'})
        agrolait = self.env.ref("base.res_partner_2")
        self.assertEqual(agrolait.online_partner_vendor_name, False)
        self.assertEqual(agrolait.online_partner_bank_account, False)
        transactions = self.create_transaction_partner(vendor_name='test_vendor_name')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id desc', limit=1)
        # Ensure that bank statement has no partner set
        self.assertEqual(created_bnk_stmt.line_ids[0].partner_id, self.env['res.partner'])
        # Assign partner and Validate bank statement
        created_bnk_stmt.line_ids[0].write({'partner_id': agrolait.id})
        # process the bank statement line
        self.confirm_bank_statement(created_bnk_stmt)
        # Check that partner has correct vendor_name associated to it
        self.assertEqual(agrolait.online_partner_vendor_name, 'test_vendor_name')
        self.assertEqual(agrolait.online_partner_bank_account, False)
        
        # Create another statement with a partner
        transactions = self.create_transaction_partner(partner_id=agrolait.id, vendor_name='test_other_vendor_name', account_number='123')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id desc', limit=1)
        # Ensure that statement has a partner set
        self.assertEqual(created_bnk_stmt.line_ids[0].partner_id, agrolait)
        # Validate and check that partner has no vendor_name set and has an account_number set instead
        self.confirm_bank_statement(created_bnk_stmt)
        self.assertEqual(agrolait.online_partner_vendor_name, False)
        self.assertEqual(agrolait.online_partner_bank_account, '123')

        # Create another statement with same information
        transactions = self.create_transaction_partner(partner_id=agrolait.id, account_number='123')
        self.bnk_stmt.online_sync_bank_statement(transactions, self.bank_journal)
        created_bnk_stmt = self.bnk_stmt.search([('journal_id','=',self.bank_journal.id)], order='id desc', limit=1)
        # Ensure that statement has a partner set
        self.assertEqual(created_bnk_stmt.line_ids[0].partner_id, agrolait)
        # Validate and check that partner has no vendor_name set and has same account_number as previous
        self.confirm_bank_statement(created_bnk_stmt)
        self.assertEqual(agrolait.online_partner_vendor_name, False)
        self.assertEqual(agrolait.online_partner_bank_account, '123')
