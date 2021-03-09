# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from unittest.mock import patch, call
from functools import reduce
from itertools import chain

from dateutil.relativedelta import relativedelta
from odoo.addons.account_auto_transfer.tests.account_auto_transfer_test_classes import AccountAutoTransferTestCase

from odoo import fields
from odoo.models import ValidationError
from odoo.tests import tagged

# ############################################################################ #
#                             FUNCTIONAL TESTS                                 #
# ############################################################################ #
@tagged('post_install', '-at_install')
class TransferModelTestFunctionalCase(AccountAutoTransferTestCase):
    def setUp(self):
        super(TransferModelTestFunctionalCase, self).setUp()
        # Model with 4 lines of 20%, 20% is left in origin accounts
        self.functional_transfer = self.env['account.transfer.model'].create({
            'name': 'Test Functional Model',
            'date_start': '2019-01-01',
            'date_stop': datetime.today() + relativedelta(months=1),
            'journal_id': self.journal.id,
            'account_ids': [(6, 0, self.origin_accounts.ids)],
            'line_ids': [(0, 0, {
                'account_id': account.id,
                'percent': 20,
            }) for account in self.destination_accounts],
        })
        neutral_account = self.env['account.account'].create({
            'name': 'Neutral Account',
            'code': 'NEUT',
            'user_type_id': self.env.ref('account.data_account_type_revenue').id,
        })
        self.analytic_accounts = reduce(lambda x, y: x + y, (self._create_analytic_account(name) for name in ('ANA1', 'ANA2', 'ANA3')))
        self.dates = ('2019-01-15', '2019-02-15')
        # Create one line for each date...
        for date in self.dates:
            # ...with each analytic account, and with no analytic account...
            for an_account in chain(self.analytic_accounts, [self.env['account.analytic.account']]):
                # ...in each origin account with a balance of 1000.
                for account in self.origin_accounts:
                    self._create_basic_move(
                        deb_account=account.id,
                        deb_analytic=an_account.id,
                        cred_account=neutral_account.id,
                        amount=1000,
                        date_str=date,
                    )

    def test_no_analytics(self):
        # Balance is +8000 in each origin account
        # 80% is transfered in 4 destination accounts in equal proprotions
        self.functional_transfer.action_perform_auto_transfer()
        # 1600 is left in each origin account
        for account in self.origin_accounts:
            self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', account.id)]).mapped('balance')), 1600)
        # 3200 has been transfered in each destination account
        for account in self.destination_accounts:
            self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', account.id)]).mapped('balance')), 3200)
            for date in self.dates:
                # 2 move lines have been created in each account for each date
                self.assertEquals(len(self.env['account.move.line'].search([('account_id', '=', account.id), ('date', '=', fields.Date.to_date(date) + relativedelta(day=1, months=1))])), 2)

    def test_analytics(self):
        # Each line with analytic accounts is set to 100%
        self.functional_transfer.line_ids[0].analytic_account_ids = self.analytic_accounts[0:2]
        self.functional_transfer.line_ids[1].analytic_account_ids = self.analytic_accounts[2]

        self.functional_transfer.action_perform_auto_transfer()
        # 1200 is left in each origin account (60% of 2 lines)
        for account in self.origin_accounts:
            self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', account.id)]).mapped('balance')), 1200)
        # 8000 has been transfered the first destination account (100% of 8 lines)
        self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', self.destination_accounts[0].id)]).mapped('balance')), 8000)
        # 4000 has been transfered the first destination account (100% of 4 lines)
        self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', self.destination_accounts[1].id)]).mapped('balance')), 4000)
        # 800 has been transfered in each of the last two destination account (20% of 4 lines)
        self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', self.destination_accounts[2].id)]).mapped('balance')), 800)
        self.assertEqual(sum(self.env['account.move.line'].search([('account_id', '=', self.destination_accounts[3].id)]).mapped('balance')), 800)


# ############################################################################ #
#                                UNIT TESTS                                    #
# ############################################################################ #
@tagged('post_install', '-at_install')
class TransferModelTestCase(AccountAutoTransferTestCase):
    @patch('odoo.addons.account_auto_transfer.models.transfer_model.TransferModel.action_perform_auto_transfer')
    def test_action_cron_auto_transfer(self, patched):
        TransferModel = self.env['account.transfer.model']
        TransferModel.create({
            'name': 'Test Cron Model',
            'date_start': '2019-01-01',
            'date_stop': datetime.today() + relativedelta(months=1),
            'journal_id': self.journal.id
        })
        TransferModel.action_cron_auto_transfer()
        patched.assert_called_once()

    @patch('odoo.addons.account_auto_transfer.models.transfer_model.TransferModel._create_or_update_move_for_period')
    def test_action_perform_auto_transfer(self, patched):
        self.transfer_model.date_start = datetime.strftime(datetime.today() + relativedelta(day=1), "%Y-%m-%d")
        # - CASE 1 : normal case, acting on current period
        self.transfer_model.action_perform_auto_transfer()
        patched.assert_not_called()  # create_or_update method should not be called for self.transfer_model as no account_ids and no line_ids

        master_ids, slave_ids = self._create_accounts(1, 2)
        self.transfer_model.write({'account_ids': [(6, 0, [master_ids.id])]})

        self.transfer_model.action_perform_auto_transfer()
        patched.assert_not_called()  # create_or_update method should not be called for self.transfer_model as no line_ids

        self.transfer_model.write({'line_ids': [
            (0, 0, {
                'percent': 50.0,
                'account_id': slave_ids[0].id
            }),
            (0, 0, {
                'percent': 50.0,
                'account_id': slave_ids[1].id
            })
        ]})

        self.transfer_model.action_perform_auto_transfer()
        patched.assert_called_once()  # create_or_update method should be called for self.transfer_model

        # - CASE 2 : "old" case, acting on everything before now as nothing has been done yet
        transfer_model = self.transfer_model.copy()
        transfer_model.write({
            'date_start': transfer_model.date_start + relativedelta(months=-12)
        })
        initial_call_count = patched.call_count
        transfer_model.action_perform_auto_transfer()
        self.assertEqual(initial_call_count + 13, patched.call_count, '13 more calls should have been done')


    @patch('odoo.addons.account_auto_transfer.models.transfer_model.TransferModel._get_auto_transfer_move_line_values')
    def test__create_or_update_move_for_period(self, patched_get_auto_transfer_move_line_values):
        # PREPARATION
        master_ids, slave_ids = self._create_accounts(2, 0)
        next_move_date = self.transfer_model._get_next_move_date(self.transfer_model.date_start)
        patched_get_auto_transfer_move_line_values.return_value = [
            {
                'account_id': master_ids[0].id,
                'date_maturity': next_move_date,
                'credit': 250.0,
            },
            {
                'account_id': master_ids[1].id,
                'date_maturity': next_move_date,
                'debit': 250.0,
            }
        ]

        # There is no existing move, this is a brand new one
        created_move = self.transfer_model._create_or_update_move_for_period(self.transfer_model.date_start, next_move_date)
        self.assertEqual(len(created_move.line_ids), 2)
        self.assertRecordValues(created_move, [{
            'date': next_move_date,
            'journal_id': self.transfer_model.journal_id.id,
            'transfer_model_id': self.transfer_model.id,
        }])
        self.assertRecordValues(created_move.line_ids.filtered(lambda l: l.credit), [{
            'account_id': master_ids[0].id,
            'date_maturity': next_move_date,
            'credit': 250.0,
        }])
        self.assertRecordValues(created_move.line_ids.filtered(lambda l: l.debit), [{
            'account_id': master_ids[1].id,
            'date_maturity': next_move_date,
            'debit': 250.0,
        }])

        patched_get_auto_transfer_move_line_values.return_value = [
            {
                'account_id': master_ids[0].id,
                'date_maturity': next_move_date,
                'credit': 78520.0,
            },
            {
                'account_id': master_ids[1].id,
                'date_maturity': next_move_date,
                'debit': 78520.0,
            }
        ]

        # Update the existing move but don't create a new one
        amount_of_moves = self.env['account.move'].search_count([])
        amount_of_move_lines = self.env['account.move.line'].search_count([])
        updated_move = self.transfer_model._create_or_update_move_for_period(self.transfer_model.date_start, next_move_date)
        self.assertEqual(amount_of_moves, self.env['account.move'].search_count([]), 'No move have been created')
        self.assertEqual(amount_of_move_lines, self.env['account.move.line'].search_count([]),
                         'No move line have been created (in fact yes but the old ones have been deleted)')
        self.assertEquals(updated_move, created_move, 'Existing move has been updated')
        self.assertRecordValues(updated_move.line_ids.filtered(lambda l: l.credit), [{
            'account_id': master_ids[0].id,
            'date_maturity': next_move_date,
            'credit': 78520.0,
        }])
        self.assertRecordValues(updated_move.line_ids.filtered(lambda l: l.debit), [{
            'account_id': master_ids[1].id,
            'date_maturity': next_move_date,
            'debit': 78520.0,
        }])

    def test__get_move_for_period(self):
        # 2019-06-30 --> None as no move generated
        date_to_test = datetime.strptime('2019-06-30', '%Y-%m-%d').date()
        move_for_period = self.transfer_model._get_move_for_period(date_to_test)
        self.assertIsNone(move_for_period, 'No move is generated yet')

        # Generate a move
        move_date = self.transfer_model._get_next_move_date(self.transfer_model.date_start)
        already_generated_move = self.env['account.move'].create({
            'date': move_date,
            'journal_id': self.journal.id,
            'transfer_model_id': self.transfer_model.id
        })
        # 2019-06-30 --> None as generated move is generated for 01/07
        move_for_period = self.transfer_model._get_move_for_period(date_to_test)
        self.assertIsNone(move_for_period, 'The generated move is for the next period')

        # 2019-07-01 --> The generated move
        date_to_test += relativedelta(days=1)
        move_for_period = self.transfer_model._get_move_for_period(date_to_test)
        self.assertEqual(move_for_period, already_generated_move, 'Should be equal to the already generated move')

        # 2019-07-02 --> None as generated move is generated for 01/07
        date_to_test += relativedelta(days=1)
        move_for_period = self.transfer_model._get_move_for_period(date_to_test)
        self.assertIsNone(move_for_period, 'No move is generated yet for the next period')

    def test__determine_start_date(self):
        start_date = self.transfer_model._determine_start_date()
        self.assertEqual(start_date, self.transfer_model.date_start, 'No moves generated yet, start date should be the start date of the transfer model')

        move = self._create_basic_move(date_str='2019-07-01', journal_id=self.journal.id, transfer_model_id=self.transfer_model.id, posted=False)
        start_date = self.transfer_model._determine_start_date()
        self.assertEqual(start_date, self.transfer_model.date_start, 'A move generated but not posted, start date should be the start date of the transfer model')

        move.post()
        start_date = self.transfer_model._determine_start_date()
        self.assertEqual(start_date, move.date, 'A move posted, start date should be the date of that move')

        second_move = self._create_basic_move(date_str='2019-08-01', journal_id=self.journal.id, transfer_model_id=self.transfer_model.id, posted=False)
        start_date = self.transfer_model._determine_start_date()
        self.assertEqual(start_date, move.date, 'Two moves generated, start date should be the date of the last posted one')

        second_move.post()
        random_move = self._create_basic_move(date_str='2019-08-01', journal_id=self.journal.id)
        start_date = self.transfer_model._determine_start_date()
        self.assertEqual(start_date, second_move.date, 'Random move generated not linked to transfer model, start date should be the date of the last one linked to it')

    def test__get_next_move_date(self):
        experimentations = {
            'month': [
                # date, expected date
                (self.transfer_model.date_start, '2019-07-01'),
                (fields.Date.to_date('2019-01-29'), '2019-02-28'),
                (fields.Date.to_date('2019-01-30'), '2019-02-28'),
                (fields.Date.to_date('2019-01-31'), '2019-02-28'),
                (fields.Date.to_date('2019-02-28'), '2019-03-28'),
                (fields.Date.to_date('2019-12-31'), '2020-01-31'),
            ],
            'quarter': [
                (self.transfer_model.date_start, '2019-09-01'),
                (fields.Date.to_date('2019-01-31'), '2019-04-30'),
                (fields.Date.to_date('2019-02-28'), '2019-05-28'),
                (fields.Date.to_date('2019-12-31'), '2020-03-31'),
            ],
            'year': [
                (self.transfer_model.date_start, '2020-06-01'),
                (fields.Date.to_date('2019-01-31'), '2020-01-31'),
                (fields.Date.to_date('2019-02-28'), '2020-02-28'),
                (fields.Date.to_date('2019-12-31'), '2020-12-31'),
            ]
        }

        for frequency in experimentations:
            self.transfer_model.write({'frequency': frequency})
            for start_date, expected_date_str in experimentations[frequency]:
                next_date = self.transfer_model._get_next_move_date(start_date)
                self.assertEqual(next_date, fields.Date.to_date(expected_date_str),
                                 'Next date from %s should be %s' % (str(next_date), expected_date_str))

    @patch('odoo.addons.account_auto_transfer.models.transfer_model.TransferModel._get_non_analytic_transfer_values')
    @patch('odoo.models.BaseModel.read_group')
    def test__get_non_analytics_auto_transfer_move_line_values(self, patched_read_group, patched_get_values):
        start_date = fields.Date.to_date('2019-01-01')
        end_date = fields.Date.to_date('2019-12-31')
        patched_read_group.return_value = [
            {'balance': 4242.42, 'account_id': (self.origin_accounts[0].id,)},
            {'balance': 0, 'account_id': (self.destination_accounts[0].id,)},
            {'balance': -12585.0, 'account_id': (self.origin_accounts[1].id,)}
        ]
        amount_left = 10.0
        patched_get_values.return_value = [{
            'name': "YO",
            'account_id': 1,
            'date_maturity': start_date,
            'debit': 123.45
        }], amount_left

        exp = [{
            'name': 'YO',
            'account_id': 1,
            'date_maturity': start_date,
            'debit': 123.45
        }, {
            'name': 'Automatic Transfer (-%s%%)' % self.transfer_model.total_percent,
            'account_id': self.origin_accounts[0].id,
            'date_maturity': end_date,
            'credit': 4242.42 - amount_left
        }, {
            'name': 'YO',
            'account_id': 1,
            'date_maturity': start_date,
            'debit': 123.45
        }, {
            'name': 'Automatic Transfer (-%s%%)' % self.transfer_model.total_percent,
            'account_id': self.origin_accounts[1].id,
            'date_maturity': end_date,
            'debit': 12585.0 - amount_left
        }]
        exp_res_len = len([x for x in patched_read_group.return_value if x['balance'] != 0.0]) * 2
        res = self.transfer_model._get_non_analytics_auto_transfer_move_line_values([], start_date, end_date)
        self.assertEqual(len(res), exp_res_len)
        self.assertListEqual(exp, res)

    @patch(
        'odoo.addons.account_auto_transfer.models.transfer_model.TransferModelLine._get_destination_account_transfer_move_line_values')
    def test__get_non_analytic_transfer_values(self, patched):
        # Just need a transfer model line
        percents = [45, 45]
        self.transfer_model.write({
            'account_ids': [(6, 0, [ma.id for ma in self.origin_accounts])],
            'line_ids': [
                (0, 0, {
                    'percent': percents[0],
                    'account_id': self.destination_accounts[0].id
                }),
                (0, 0, {
                    'percent': percents[1],
                    'account_id': self.destination_accounts[1].id
                })
            ]
        })
        account = self.origin_accounts[0]
        write_date = fields.Date.to_date('2019-01-01')
        lines = self.transfer_model.line_ids
        amount_of_line = len(lines)
        amount = 4242.0
        is_debit = False
        patched.return_value = {
            'name': "YO",
            'account_id': account.id,
            'date_maturity': write_date,
            'debit' if is_debit else 'credit': amount
        }
        expected_result_list = [patched.return_value] * 2
        expected_result_amount = amount * ((100.0 - sum(percents)) / 100.0)

        res = self.transfer_model._get_non_analytic_transfer_values(account, lines, write_date, amount, is_debit)
        self.assertListEqual(res[0], expected_result_list)
        self.assertAlmostEqual(res[1], expected_result_amount)
        self.assertEqual(patched.call_count, amount_of_line)

        # need to round amount to avoid failing float comparison (as magic mock uses "==" to compare args)
        exp_calls = [call(account, round(amount * (line.percent / 100.0), 1), is_debit, write_date) for line in lines]
        patched.assert_has_calls(exp_calls)

        # Try now with 100% repartition
        lines[0].write({'percent': 55.0})
        res = self.transfer_model._get_non_analytic_transfer_values(account, lines, write_date, amount, is_debit)
        self.assertAlmostEqual(res[1], 0.0)

    # TEST CONSTRAINTS
    def test__check_line_ids_percents(self):
        with self.assertRaises(ValidationError):
            transfer_model_lines = []
            for i, percent in enumerate((50.0, 50.01)):
                transfer_model_lines.append((0, 0, {
                    'percent': percent,
                    'account_id': self.destination_accounts[i].id
                }))
            self.transfer_model.write({
                'account_ids': [(6, 0, [ma.id for ma in self.origin_accounts])],
                'line_ids': transfer_model_lines
            })
