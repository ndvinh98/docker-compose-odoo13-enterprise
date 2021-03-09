# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch
from odoo.exceptions import UserError
from odoo.addons.account.tests.account_test_classes import AccountingTestCase
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.tests import tagged
from odoo import fields
import requests
import json

class MockResponse:
    def __init__(self, url, text, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.text = text
        self.url = url

    def json(self):
        if type(self.json_data) == dict:
            return self.json_data
        else:
            raise ValueError

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(self)


@tagged('post_install', '-at_install')
class TestPlaidApi(AccountingTestCase):

    def setUp(self):
        super(TestPlaidApi, self).setUp()
        self.db_name = self.env.cr.dbname
        self.db_uid = self.env['ir.config_parameter'].get_param('database.uuid')
        self.url = 'https://onlinesync.odoo.com/plaid/api/2'
        self.payment_meta = False
        self.online_identifier = "lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDje"

    def create_account_provider(self):
        return self.env['account.online.provider'].create({
            'name': 'test', 
            'provider_type': 'plaid', 
            'provider_account_identifier': '123',
            'plaid_item_id': 'item123',
            'provider_identifier': 'inst_1',
            'status': 'SUCCESS',
            'status_code': 0,
            'account_online_journal_ids': [
                (0, 0, {'name': 'myAccount', 
                    'account_number': '0000', 
                    'online_identifier': '456', 
                    'balance': 500.0, 
                    'last_sync': datetime.today() - relativedelta(days=15)})
            ]
        })

    # Method that simulate succesfull requests.post and response .
    def plaid_post(self, *args, **kwargs):
        jsondata = json.loads(kwargs.get('data'))
        if args[0] == self.url + '/item/public_token/exchange':
            self.assertEqual(jsondata, {'secret': self.db_uid, 'client_id': self.db_name, 'public_token': 'public-sandbox-019e1018-be47-4842-aada-1dea2ee0ab22'}, 
                'Call to /item/public_token/exchange with wrong json params')
            resp = {
                'access_token': 'access-sandbox-de3ce8ef-33f8-452c-a685-8671031fc0f6',
                'item_id': 'M5eVJqLnv3tbzdngLDp9FL5OlDNxlNhlE55op',
                'request_id': 'Aim3b',
            }
            return MockResponse(args[0], '', resp, 200)
        elif args[0] == self.url +'/accounts/balance/get':
            expected_json = {
                'secret': self.db_uid, 
                'client_id': self.db_name, 
                'access_token': 'access-sandbox-de3ce8ef-33f8-452c-a685-8671031fc0f6',
                'options': {'account_ids': ['QKKzevvp33HxPWpoqn6rI13BxW4awNSjnw4xv']}
            }
            self.assertEqual(jsondata, expected_json, 
                'Call to /accounts/balance/get with wrong json params')
            resp = {
              "accounts": [{
                 "account_id": "QKKzevvp33HxPWpoqn6rI13BxW4awNSjnw4xv",
                 "balances": {
                   "available": 100,
                   "current": 110,
                   "limit": 'null'
                 },
                 "mask": "0000",
                 "name": "Plaid Checking",
                 "official_name": "Plaid Gold Checking",
                 "subtype": "checking",
                 "type": "depository"
              }],
              "item": {'id': 'M5eVJqLnv3tbzdngLDp9FL5OlDNxlNhlE55op'},
              "request_id": "1zlMf"
            }
            return MockResponse(args[0], '', resp, 200)
        elif args[0] == self.url + '/transactions/get':
            offset = jsondata.get('options',{}).get('offset', 0)
            expected_json = {
                'secret': self.db_uid, 
                'client_id': self.db_name, 
                'access_token': '123',
                'start_date': datetime.strftime(datetime.today() - relativedelta(days=15), '%Y-%m-%d'),
                'end_date': datetime.strftime(datetime.today(), '%Y-%m-%d'),
                'options': {'account_ids': ['456'], 'count': 500, 'offset': offset}
            }
            self.assertEqual(jsondata, expected_json, 'Call to /transactions/get with wrong json params')
            resp = {
             "accounts": [{
                'account_id': '456',
                'balances': {'current': 230},
             }],
             "transactions": [{
                "account_id": "456",
                "amount": 2307.21,
                "category": [
                  "Shops",
                  "Computers and Electronics"
                ],
                "category_id": "19013000",
                "date": datetime.strftime(datetime.today(), '%Y-%m-%d'),
                "location": {
                 "address": "300 Post St",
                 "city": "San Francisco",
                 "zip": "94108",
                 "lat": "0",
                 "lon": "0"
                },
                "name": "Damdoum Store",
                "payment_meta": self.payment_meta,
                "pending": False,
                "pending_transaction_id": False,
                "account_owner": False,
                "transaction_id": str(offset)+self.online_identifier,
                "transaction_type": "place"
               }],
              "item": {'id': 'M5eVJqLnv3tbzdngLDp9FL5OlDNxlNhlE55op'},
              "total_transactions": 1230,
              "request_id": "45QSn"
            }
            return MockResponse(args[0], '', resp, 200)
        else:
            self.assertEqual(args[0], ' ', 'Call to that url not supposed to happen')

    def plaid_post_error(self, *args, **kwargs):
        if (args[0].endswith('error_plaid')):
            error = {
              "error_type": "API_ERROR",
              "http_code": 500,
              "error_code": "INTERNAL_SERVER_ERROR",
              "error_message": "Some random error text",
              "display_message": "Explained error text",
              "request_id": "12345"
            }
            return MockResponse(args[0], '', error, 500)
        elif (args[0].endswith('no_contract')):
            return MockResponse(args[0], 'No valid Odoo Enterprise contract found for this database', {}, 403)
        elif (args[0].endswith('error_plaid2')):
            error = { 
                "error": {
                    "error_type": "INSTITUTION_ERROR",
                    "http_code": 400,
                    "error_code": "INSTITUTION_DOWN",
                    "error_message": "Site is down",
                    "display_message": "Site is down",
                    "request_id": "12345"
                }
            }
            return MockResponse(args[0], '', error, 500)
        return MockResponse(args[0], 'A wild error has happened, do you want to catch it?', 'no_json', 432)


    def test_plaid_create_institution(self):
        """ Test adding a new institution with plaid """
        # Simulate a user that just complete the authentication process with plaid, wa have received a token and a list
        # Of account_ids and need to exchange the token to get the id identifying the user in plaid database and then create
        # the account.online.provider with the linked accounts in Odoo
        
        # Patch request.post with defined method
        patcher = patch('odoo.addons.account_plaid.models.plaid.requests.post', side_effect=self.plaid_post)
        patcher.start()
        metadata = {
            'link_session_id': '378547f9-7a1a-4edd-a566-3a9bf99284c8', 
            'account': {'name': 'Plaid Checking', 'id': 'QKKzevvp33HxPWpoqn6rI13BxW4awNSjnw4xv', 'type': 'depository'}, 
            'public_token': 'public-sandbox-019e1018-be47-4842-aada-1dea2ee0ab22', 
            'accounts': [{'name': 'Plaid Checking', 'id': 'QKKzevvp33HxPWpoqn6rI13BxW4awNSjnw4xv', 'type': 'depository'}], 
            'institution': {'name': 'Chase', 'institution_id': 'ins_3'}, 
            'account_id': 'QKKzevvp33HxPWpoqn6rI13BxW4awNSjnw4xv'
            }
        result = self.env['account.online.provider'].link_success('public-sandbox-019e1018-be47-4842-aada-1dea2ee0ab22', metadata)

        acc_online_provider = self.env['account.online.provider'].search([])
        self.assertEqual(len(acc_online_provider), 1, 'An account_online_provider should have been created')
        self.assertEqual(acc_online_provider.name, 'Chase')
        self.assertEqual(acc_online_provider.provider_type, 'plaid')
        self.assertEqual(acc_online_provider.provider_account_identifier, 'access-sandbox-de3ce8ef-33f8-452c-a685-8671031fc0f6')
        self.assertEqual(acc_online_provider.plaid_item_id, 'M5eVJqLnv3tbzdngLDp9FL5OlDNxlNhlE55op')
        self.assertEqual(acc_online_provider.provider_identifier, 'ins_3')
        self.assertEqual(acc_online_provider.status, 'SUCCESS')
        self.assertEqual(acc_online_provider.status_code, '0')
        self.assertEqual(len(acc_online_provider.account_online_journal_ids), 1, 'An account should have been created with the account_online_provider')
        self.assertEqual(acc_online_provider.account_online_journal_ids.name, 'Plaid Checking')
        self.assertEqual(acc_online_provider.account_online_journal_ids.account_number, '0000')
        self.assertEqual(acc_online_provider.account_online_journal_ids.online_identifier, 'QKKzevvp33HxPWpoqn6rI13BxW4awNSjnw4xv')
        self.assertEqual(acc_online_provider.account_online_journal_ids.balance, 100.0)

        patcher.stop()
        return True

    def test_plaid_fetch_transactions(self):
        """ Test receiving some transactions with plaid """
        # Create fake account.online.provider
        bank_journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1) or False
        acc_online_provider = self.create_account_provider()
        if bank_journal:
            account_online_journal = self.env['account.online.journal'].search([], limit=1)
            bank_journal.write({'account_online_journal_id': account_online_journal.id})
        else:
            # No localization installed, so skip test
            return True

        # Patch request.post with defined method
        patcher = patch('odoo.addons.account_plaid.models.plaid.requests.post', side_effect=self.plaid_post)
        patcher.start()

        ret = acc_online_provider.manual_sync()
        # Check that we've a bank statement with 3 lines (we assumed that the demo data have been loaded and a
        # bank statement has already been created, otherwise the statement should have 4 lines as a new one for
        # opening entry will be created)
        bank_stmt = self.env['account.bank.statement'].search([('name', '=', 'online sync')], order="create_date desc")
        self.assertEqual(len(bank_stmt), 1, 'There should be at least one bank statement created')
        self.assertEqual(len(bank_stmt.line_ids), 3, 'The statement should have 3 lines')
        self.assertEqual(bank_stmt.state, 'open')
        self.assertEqual(bank_stmt.journal_id.id, bank_journal.id)
        for i in range(0,3):
            self.assertEqual(bank_stmt.line_ids[i].name, 'Damdoum Store')
            self.assertEqual(bank_stmt.line_ids[i].amount, -2307.21)
            self.assertTrue(bank_stmt.line_ids[i].online_identifier.endswith("lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDje"))
            self.assertEqual(bank_stmt.line_ids[i].partner_id, self.env['res.partner']) #No partner defined on line
        self.assertEqual(account_online_journal.last_sync, fields.Date.today())
            
        # Call again and check that we don't have any new transactions
        account_online_journal.last_sync = fields.Date.today() - relativedelta(days=15)
        acc_online_provider.manual_sync()
        bank_stmt = self.env['account.bank.statement'].search([('name', '=', 'online sync')], order="create_date desc")
        self.assertEqual(len(bank_stmt), 1, 'There should not be a new statement created')
        self.assertEqual(len(bank_stmt.line_ids), 3, 'The existing statement should still have 3 lines')
        patcher.stop()
        return True

    def test_plaid_fetch_errors(self):
        """ Test some plaid error that might happen """
        # Patch request.post with defined method
        patcher = patch('odoo.addons.account_plaid.models.plaid.requests.post', side_effect=self.plaid_post_error)
        patcher.start()

        with self.assertRaises(UserError) as e:
            self.env['account.online.provider'].plaid_fetch('/error_plaid', {})
        self.assertEqual(e.exception.name, 'There was en error with Plaid Services!\n{message: Explained error text,\nerror code: INTERNAL_SERVER_ERROR,\nerror type: API_ERROR,\nrequest id: 12345}')

        with self.assertRaises(UserError) as e:
            self.env['account.online.provider'].plaid_fetch('/error_plaid2', {})
        self.assertEqual(e.exception.name, 'There was en error with Plaid Services!\n{message: Site is down,\nerror code: INSTITUTION_DOWN,\nerror type: INSTITUTION_ERROR,\nrequest id: 12345}')

        with self.assertRaises(UserError) as e:
            self.env['account.online.provider'].plaid_fetch('/no_contract', {})
        self.assertEqual(e.exception.name, 'No valid Odoo Enterprise contract found for this database')

        with self.assertRaises(UserError) as e:
            self.env['account.online.provider'].plaid_fetch('/pokemon', {})
        exc_msg = 'Get %s status code for call to %s. Content message: %s' % (432, self.url+'/pokemon', 'A wild error has happened, do you want to catch it?')
        self.assertEqual(e.exception.name, exc_msg)

        # Test errors with a provider existing and check that the status has changed to 'FAILED'
        acc_online_provider = self.create_account_provider()
        self.assertEqual(acc_online_provider.status, 'SUCCESS', 'state of account online provider should be in SUCCESS')
        self.assertEqual(acc_online_provider.action_required, False, 'account_online_provider should have the flag action_required set to False')

        with self.assertRaises(UserError) as e:
            acc_online_provider.plaid_fetch('/error_plaid', {})
        self.assertEqual(acc_online_provider.status, 'FAILED', 'state of account_online_provider should have change to FAILED')
        self.assertEqual(acc_online_provider.action_required, True, 'account_online_provider should have the flag action_required set to True')
        
        # Reset state to success
        acc_online_provider.status = 'SUCCESS'
        self.assertEqual(acc_online_provider.status, 'SUCCESS', 'state of account online provider should be in SUCCESS')
        acc_online_provider.flush(['status'])
        with self.assertRaises(UserError) as e:
            acc_online_provider.plaid_fetch('/error_plaid2', {})
        self.assertEqual(acc_online_provider.status, 'FAILED', 'state of account_online_provider should have change to FAILED')

        # Reset state to success
        acc_online_provider.status = 'SUCCESS'
        self.assertEqual(acc_online_provider.status, 'SUCCESS', 'state of account online provider should be in SUCCESS')
        acc_online_provider.flush(['status'])
        with self.assertRaises(UserError) as e:
            acc_online_provider.plaid_fetch('/no_contract', {})
        self.assertEqual(acc_online_provider.status, 'FAILED', 'state of account_online_provider should have change to FAILED')

        # Reset state to success
        acc_online_provider.status = 'SUCCESS'
        self.assertEqual(acc_online_provider.status, 'SUCCESS', 'state of account online provider should be in SUCCESS')
        with self.assertRaises(UserError) as e:
            acc_online_provider.plaid_fetch('/pokemon', {})
        self.assertEqual(acc_online_provider.status, 'SUCCESS', 'state of account_online_provider should still be SUCCESS')

        patcher.stop()
        return True

    def test_assign_partner_automatically(self):
        """ Test receiving some transactions with plaid and assigning partner"""
        # Create fake account.online.provider
        bank_journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1) or False
        acc_online_provider = self.create_account_provider()
        if bank_journal:
            account_online_journal = self.env['account.online.journal'].search([], limit=1)
            bank_journal.write({'account_online_journal_id': account_online_journal.id})
        else:
            # No localization installed, so skip test
            return True

        self.payment_meta = {'payee_name': '123'}

        agrolait = self.env.ref("base.res_partner_2")

        # set online data on partner to simulate previous synchronization linked to agrolait
        agrolait.write({'online_partner_vendor_name': '123'})

        # Patch request.post with defined method
        patcher = patch('odoo.addons.account_plaid.models.plaid.requests.post', side_effect=self.plaid_post)
        patcher.start()

        ret = acc_online_provider.manual_sync()
        # Check that we've a bank statement with 3 lines (we assumed that the demo data have been loaded and a
        # bank statement has already been created, otherwise the statement should have 4 lines as a new one for
        # opening entry will be created)
        bank_stmt = self.env['account.bank.statement'].search([('name', '=', 'online sync')], order="create_date desc")
        self.assertEqual(len(bank_stmt), 1, 'There should be at least one bank statement created')
        self.assertEqual(len(bank_stmt.line_ids), 3, 'The statement should have 3 lines')
        self.assertEqual(bank_stmt.state, 'open')
        self.assertEqual(bank_stmt.journal_id.id, bank_journal.id)
        for i in range(0,3):
            self.assertTrue(bank_stmt.line_ids[i].online_identifier.endswith("lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDje"))
            self.assertEqual(bank_stmt.line_ids[i].partner_id, agrolait)
        bank_stmt.unlink()

        # Check that partner assignation also work with location
        self.payment_meta = False
        self.online_identifier = 'lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDjf'
        ASUSTeK = self.env.ref("base.res_partner_1")
        ASUSTeK.write({'street': '300 Post St', 'city': 'San Francisco', 'zip': '94108'})
        acc_online_provider.account_online_journal_ids[0].write({'last_sync': datetime.today() - relativedelta(days=15)})
        ret = acc_online_provider.manual_sync()
        bank_stmt = self.env['account.bank.statement'].search([('name', '=', 'online sync')], order="create_date desc", limit=1)
        self.assertEqual(len(bank_stmt.line_ids), 3, 'The statement should have 3 lines')
        for i in range(0,3):
            self.assertTrue(bank_stmt.line_ids[i].online_identifier.endswith("lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDjf"))
            self.assertEqual(bank_stmt.line_ids[i].partner_id, ASUSTeK)
        bank_stmt.unlink()

        # Check that if we have both partner with same info, no partner is displayed
        self.payment_meta = {'payee_name': '123'}
        self.online_identifier = 'lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDja'
        ASUSTeK.write({'online_partner_vendor_name': '123', 'street': False, 'city': False, 'zip': False})
        acc_online_provider.account_online_journal_ids[0].write({'last_sync': datetime.today() - relativedelta(days=15)})
        ret = acc_online_provider.manual_sync()
        bank_stmt = self.env['account.bank.statement'].search([('name', '=', 'online sync')], order="create_date desc", limit=1)
        self.assertEqual(len(bank_stmt.line_ids), 3, 'The statement should have 3 lines')
        for i in range(0,3):
            self.assertTrue(bank_stmt.line_ids[i].online_identifier.endswith("lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDja"))
            self.assertEqual(bank_stmt.line_ids[i].partner_id, self.env['res.partner'])
        bank_stmt.unlink()

        # Check that vendor name take precedence over location
        ASUSTeK.write({'street': '300 Post St', 'city': 'San Francisco', 'zip': '94108', 'online_partner_vendor_name': False})
        self.online_identifier = 'lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDjb'
        acc_online_provider.account_online_journal_ids[0].write({'last_sync': datetime.today() - relativedelta(days=15)})
        ret = acc_online_provider.manual_sync()
        bank_stmt = self.env['account.bank.statement'].search([('name', '=', 'online sync')], order="create_date desc", limit=1)
        self.assertEqual(len(bank_stmt.line_ids), 3, 'The statement should have 3 lines')
        for i in range(0,3):
            self.assertTrue(bank_stmt.line_ids[i].online_identifier.endswith("lPNjeW1nR6CDn5okmGQ6hEpMo4lLNoSrzqDjb"))
            self.assertEqual(bank_stmt.line_ids[i].partner_id, agrolait)

        patcher.stop()
        return True
