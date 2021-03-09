# -*- coding: utf-8 -*-
from datetime import datetime
from uuid import uuid4

from odoo.tests import common


class AccountAutoTransferTestCase(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.journal = self.env['account.journal'].create({'type': 'bank', 'name': 'bank', 'code': 'BANK'})
        self.transfer_model = self.env['account.transfer.model'].create({
            'name': 'Test Transfer',
            'date_start': '2019-06-01',
            'frequency': 'month',
            'journal_id': self.journal.id
        })
        self.master_account_index = 0
        self.slave_account_index = 1
        self.origin_accounts, self.destination_accounts = self._create_accounts()

    def _assign_origin_accounts(self):
        self.transfer_model.write({
            'account_ids': [(6, 0, self.origin_accounts.ids)]
        })

    def _create_accounts(self, amount_of_master_accounts=2, amount_of_slave_accounts=4):
        account_type = self.env.ref('account.data_account_type_receivable')

        master_ids = self.env['account.account']
        for i in range(amount_of_master_accounts):
            self.master_account_index += 1
            master_ids += self.env['account.account'].create({
                'name': 'MASTER %s' % self.master_account_index,
                'code': 'MA00%s' % self.master_account_index,
                'user_type_id': account_type.id,
                'reconcile': True
            })

        slave_ids = self.env['account.account']
        for i in range(amount_of_slave_accounts):
            self.slave_account_index += 1
            slave_ids += self.env['account.account'].create({
                'name': 'SLAVE %s' % self.slave_account_index,
                'code': 'SL000%s' % self.slave_account_index,
                'user_type_id': account_type.id,
                'reconcile': True
            })
        return master_ids, slave_ids

    def _create_analytic_account(self, code='ANAL01'):
        return self.env['account.analytic.account'].create({'name': code, 'code': code})

    def _create_basic_move(self, cred_account=None, deb_account=None, amount=0, date_str='2019-02-01',
                           name=False, cred_analytic=False, deb_analytic=False, transfer_model_id=False, journal_id=False, posted=True):
        move_vals = {
            'date': date_str,
            'transfer_model_id': transfer_model_id,
            'line_ids': [
                (0, 0, {
                    'account_id': cred_account or self.origin_accounts[0].id,
                    'credit': amount,
                    'analytic_account_id': cred_analytic
                }),
                (0, 0, {
                    'account_id': deb_account or self.origin_accounts[1].id,
                    'analytic_account_id': deb_analytic,
                    'debit': amount
                }),
            ]
        }
        if journal_id:
            move_vals['journal_id'] = journal_id
        move = self.env['account.move'].create(move_vals)
        if posted:
            move.post()
        return move

    def _add_transfer_model_line(self, account_id: int = False, percent: float = 100.0, analytic_account_ids: list = False):
        account_id = account_id or self.destination_accounts[0].id
        if not analytic_account_ids or len(analytic_account_ids) == 0:
            return self.env['account.transfer.model.line'].create({
                'percent': percent,
                'account_id': account_id,
                'transfer_model_id': self.transfer_model.id
            })
        return self.env['account.transfer.model.line'].create({
            'percent': 0,
            'account_id': account_id,
            'transfer_model_id': self.transfer_model.id,
            'analytic_account_ids': [(4, aa) for aa in analytic_account_ids],
        })
