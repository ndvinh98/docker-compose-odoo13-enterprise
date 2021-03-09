# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import psycopg2

from odoo import _, api, models
from odoo.exceptions import UserError


class AccountBankStatementImport(models.TransientModel):
    _inherit = "account.bank.statement.import"

    def _check_csv(self, filename):
        return filename and filename.lower().strip().endswith('.csv')

    def import_file(self):
        # In case of CSV files, only one file can be imported at a time.
        if len(self.attachment_ids) > 1:
            csv = [bool(self._check_csv(att.name)) for att in self.attachment_ids]
            if True in csv and False in csv:
                raise UserError(_('Mixing CSV files with other file types is not allowed.'))
            if csv.count(True) > 1:
                raise UserError(_('Only one CSV file can be selected.'))
            return super(AccountBankStatementImport, self).import_file()

        if not self._check_csv(self.attachment_ids.name):
            return super(AccountBankStatementImport, self).import_file()
        ctx = dict(self.env.context)
        import_wizard = self.env['base_import.import'].create({
            'res_model': 'account.bank.statement.line',
            'file': base64.b64decode(self.attachment_ids.datas),
            'file_name': self.attachment_ids.name,
            'file_type': 'text/csv'
        })
        ctx['wizard_id'] = import_wizard.id
        return {
            'type': 'ir.actions.client',
            'tag': 'import_bank_stmt',
            'params': {
                'model': 'account.bank.statement.line',
                'context': ctx,
                'filename': self.attachment_ids.name,
            }
        }


class AccountBankStmtImportCSV(models.TransientModel):

    _inherit = 'base_import.import'

    @api.model
    def get_fields(self, model, depth=2):
        fields_list = super(AccountBankStmtImportCSV, self).get_fields(model, depth=depth)
        if self._context.get('bank_stmt_import', False):
            add_fields = [{
                'id': 'balance',
                'name': 'balance',
                'string': 'Cumulative Balance',
                'required': False,
                'fields': [],
                'type': 'monetary',
            }, {
                'id': 'debit',
                'name': 'debit',
                'string': 'Debit',
                'required': False,
                'fields': [],
                'type': 'monetary',
            }, {
                'id': 'credit',
                'name': 'credit',
                'string': 'Credit',
                'required': False,
                'fields': [],
                'type': 'monetary',
            }]
            fields_list.extend(add_fields)
        return fields_list

    def _convert_to_float(self, value):
        return float(value) if value else 0.0

    def _parse_import_data(self, data, import_fields, options):
        data = super(AccountBankStmtImportCSV, self)._parse_import_data(data, import_fields, options)
        statement_id = self._context.get('bank_statement_id', False)
        if not statement_id:
            return data
        statement = self.env['account.bank.statement'].browse(statement_id)
        company_currency_name = statement.company_id.currency_id.name
        ret_data = []

        vals = {}
        import_fields.append('statement_id/.id')
        import_fields.append('sequence')
        index_balance = False
        convert_to_amount = False
        if 'debit' in import_fields and 'credit' in import_fields:
            index_debit = import_fields.index('debit')
            index_credit = import_fields.index('credit')
            self._parse_float_from_data(data, index_debit, 'debit', options)
            self._parse_float_from_data(data, index_credit, 'credit', options)
            import_fields.append('amount')
            convert_to_amount = True
        # add starting balance and ending balance to context
        if 'balance' in import_fields:
            index_balance = import_fields.index('balance')
            self._parse_float_from_data(data, index_balance, 'balance', options)
            vals['balance_start'] = self._convert_to_float(data[0][index_balance])
            vals['balance_start'] -= self._convert_to_float(data[0][import_fields.index('amount')]) \
                                            if not convert_to_amount \
                                            else abs(self._convert_to_float(data[0][index_debit]))-abs(self._convert_to_float(data[0][index_credit]))
            vals['balance_end_real'] = data[len(data)-1][index_balance]
            import_fields.remove('balance')
        # Remove debit/credit field from import_fields
        if convert_to_amount:
            import_fields.remove('debit')
            import_fields.remove('credit')

        currency_index = 'currency_id' in import_fields and import_fields.index('currency_id') or False
        for index, line in enumerate(data):
            line.append(statement_id)
            line.append(index)
            remove_index = []
            if convert_to_amount:
                line.append(
                    abs(self._convert_to_float(line[index_credit]))
                    - abs(self._convert_to_float(line[index_debit]))
                )
                remove_index.extend([index_debit, index_credit])
            if index_balance:
                remove_index.append(index_balance)
            # Remove added field debit/credit/balance
            for index in sorted(remove_index, reverse=True):
                line.remove(line[index])
            if line[import_fields.index('amount')]:
                ret_data.append(line)
            # Don't set the currency_id on statement line if the currency is the same as the company one.
            if currency_index is not False and line[currency_index] == company_currency_name:
                line[currency_index] = False
        if 'date' in import_fields:
            vals['date'] = data[len(data)-1][import_fields.index('date')]

        # add starting balance and date if there is one set in fields
        if vals:
            statement.write(vals)
        return ret_data

    def parse_preview(self, options, count=10):
        if options.get('bank_stmt_import', False):
            self = self.with_context(bank_stmt_import=True)
        return super(AccountBankStmtImportCSV, self).parse_preview(options, count=count)

    def do(self, fields, columns, options, dryrun=False):
        if options.get('bank_stmt_import', False):
            self._cr.execute('SAVEPOINT import_bank_stmt')
            vals = {
                'journal_id': self._context.get('journal_id', False),
                'reference': self.file_name
            }
            statement = self.env['account.bank.statement'].create(vals)
            res = super(AccountBankStmtImportCSV, self.with_context(bank_statement_id=statement.id)).do(fields, columns, options, dryrun=dryrun)

            try:
                if dryrun:
                    self._cr.execute('ROLLBACK TO SAVEPOINT import_bank_stmt')
                else:
                    self._cr.execute('RELEASE SAVEPOINT import_bank_stmt')
                    res['messages'].append({
                        'statement_id': statement.id,
                        'type': 'bank_statement'
                        })
            except psycopg2.InternalError:
                pass
            return res
        else:
            return super(AccountBankStmtImportCSV, self).do(fields, columns, options, dryrun=dryrun)
