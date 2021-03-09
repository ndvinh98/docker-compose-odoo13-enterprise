# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.modules.module import get_module_resource


class TestCSVFile(TransactionCase):
    """ Tests for import bank statement ofx file format (account.bank.statement.import) """

    def test_csv_file_import(self):
        # Get OFX file content
        csv_file_path = get_module_resource('account_bank_statement_import_csv', 'test_csv_file', 'test_csv.csv')
        csv_file = open(csv_file_path, 'rb').read()

        # Create a bank account and journal corresponding to the CSV file (same currency and account number)
        bank_journal = self.env['account.journal'].create({'name': 'Bank 123456', 'code': 'BNK67', 'type': 'bank',
            'bank_acc_number': '123456'})
        bank_journal_id = bank_journal.id
        if bank_journal.company_id.currency_id != self.env.ref("base.USD"):
            bank_journal.write({'currency_id': self.env.ref("base.USD").id})

        # Use an import wizard to process the file
        import_wizard = self.env['base_import.import'].create({'res_model': 'account.bank.statement.line',
                                                'file': csv_file,
                                                'file_name': 'test_csv.csv',
                                                'file_type': 'text/csv'})

        options = {
            'date_format': '%m %d %y',
            'keep_matches': False,
            'encoding': 'utf-8',
            'fields': [],
            'quoting': '"',
            'bank_stmt_import': True,
            'headers': True,
            'separator': ';',
            'float_thousand_separator': ',',
            'float_decimal_separator': '.',
            'advanced': False}
        fields = ['date', False, 'name', 'amount', 'balance']
        import_wizard.with_context(journal_id=bank_journal_id).do(fields, [], options, dryrun=False)

        # Check the imported bank statement
        bank_st_record = self.env['account.bank.statement'].search([('reference', '=', 'test_csv.csv')])[0]
        self.assertEqual(bank_st_record.balance_start, 21699.55)
        self.assertEqual(bank_st_record.balance_end_real, 23462.55)

        # Check an imported bank statement line
        line = bank_st_record.line_ids.filtered(lambda r: r.name == 'ACH CREDIT"CHECKFLUID INC -013015')
        self.assertEqual(str(line.date), '2015-02-03')
        self.assertEqual(line.amount, 2500.00)
