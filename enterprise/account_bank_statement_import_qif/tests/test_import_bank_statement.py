# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo.tests.common import TransactionCase
from odoo.modules.module import get_module_resource


class TestQifFile(TransactionCase):
    """Tests for import bank statement qif file format (account.bank.statement.import)
    """

    def setUp(self):
        super(TestQifFile, self).setUp()
        self.BankStatement = self.env['account.bank.statement']
        self.BankStatementLine = self.env['account.bank.statement.line']

    def test_qif_file_import(self):
        qif_file_path = get_module_resource('account_bank_statement_import_qif', 'static/qif', 'test_qif.qif')
        qif_file = base64.b64encode(open(qif_file_path, 'rb').read())

        bank_journal = self.env['account.journal'].create({'type': 'bank', 'name': 'bank QIF', 'code': 'BNK67'})
        self.env['account.bank.statement.import'].with_context(journal_id=bank_journal.id).create({'attachment_ids': [(0, 0, {
            'name': 'test file',
            'datas': qif_file,
        })]}).import_file()
        line = self.BankStatementLine.search([('name', '=', 'YOUR LOCAL SUPERMARKET')], limit=1)
        self.assertAlmostEqual(line.statement_id.balance_end_real, -1896.09)
