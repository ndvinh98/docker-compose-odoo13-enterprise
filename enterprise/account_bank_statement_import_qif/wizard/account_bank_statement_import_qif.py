# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import logging

import dateutil.parser

from odoo import api, fields, models, _
from odoo.exceptions import UserError


logger = logging.getLogger(__name__)
class AccountBankStatementImport(models.TransientModel):
    _inherit = "account.bank.statement.import"

    def _get_hide_journal_field(self):
        return self.env.context and 'journal_id' in self.env.context or False

    journal_id = fields.Many2one('account.journal', string='Journal',
        help="Accounting journal related to the bank statement you're importing. It has to be manually chosen "
             "for statement formats which doesn't allow automatic journal detection (QIF for example).")
    hide_journal_field = fields.Boolean(string='Hide the journal field in the view', default=_get_hide_journal_field)

    show_qif_date_format = fields.Boolean(default=False, store=False,
        help="Technical field used to ask the user for the date format used in the QIF file, as this format is ambiguous.")
    qif_date_format = fields.Selection([('month_first', "mm/dd/yy"), ('day_first', "dd/mm/yy")], string='Dates format', required=True, store=False,
        help="Although the historic QIF date format is month-first (mm/dd/yy), many financial institutions use the local format."
             "Therefore, it is frequent outside the US to have QIF date formated day-first (dd/mm/yy).")

    @api.onchange('attachment_ids')
    def _onchange_data_file(self):
        file_contents = self.attachment_ids.mapped('datas')
        self.show_qif_date_format = any(self._check_qif(base64.b64decode(content)) for content in file_contents)

    def _find_additional_data(self, *args):
        """ As .QIF format does not allow us to detect the journal, we need to let the user choose it.
            We set it in context in the same way it's done when calling the import action from a journal.
        """
        if self.journal_id:
            self.env.context = dict(self.env.context, journal_id=self.journal_id.id)
        return super(AccountBankStatementImport, self)._find_additional_data(*args)

    def _check_qif(self, data_file):
        return data_file.strip().startswith(b'!Type:')

    def _parse_file(self, data_file):
        if not self._check_qif(data_file):
            return super(AccountBankStatementImport, self)._parse_file(data_file)

        data_list = [
            line.rstrip(b'\r\n')
            for line in io.BytesIO(data_file)
        ]
        try:
            header = data_list[0].strip().split(b':')[1]
        except:
            raise UserError(_('Could not decipher the QIF file.'))

        transactions = []
        vals_line = {'name': []}
        total = 0.0
        # Identified header types of the QIF format that we support.
        # Other types might need to be added. Here are the possible values
        # according to the QIF spec: Cash, Bank, CCard, Invst, Oth A, Oth L, Invoice.
        if header in [b'Bank', b'Cash', b'CCard']:
            vals_bank_statement = {}
            for line in data_list:
                line = line.strip()
                if not line:
                    continue
                vals_line['sequence'] = len(transactions) + 1
                data = line[1:]
                if line[:1] == DATE_OF_TRANSACTION:
                    dayfirst = self.env.context.get('qif_date_format') == 'day_first'
                    vals_line['date'] = dateutil.parser.parse(data, fuzzy=True, dayfirst=dayfirst).date()
                elif line[:1] == TOTAL_AMOUNT:
                    amount = float(data.replace(b',', b''))
                    total += amount
                    vals_line['amount'] = amount
                elif line[:1] == CHECK_NUMBER:
                    vals_line['ref'] = data.decode('utf-8')
                elif line[:1] == PAYEE:
                    name = data.decode('utf-8')
                    vals_line['name'].append(name)
                    # Since QIF doesn't provide account numbers, we'll have to find res.partner and res.partner.bank here
                    # (normal behavious is to provide 'account_number', which the generic module uses to find partner/bank)
                    partner_bank = self.env['res.partner.bank'].search([('partner_id.name', '=', name)], limit=1)
                    if partner_bank:
                        vals_line['bank_account_id'] = partner_bank.id
                        vals_line['partner_id'] = partner_bank.partner_id.id
                elif line[:1] == MEMO:
                    vals_line['name'].append(data.decode('utf-8'))
                elif line[:1] == END_OF_ITEM:
                    if vals_line['name']:
                        vals_line['name'] = u': '.join(vals_line['name'])
                    else:
                        del vals_line['name']
                    transactions.append(vals_line)
                    vals_line = {'name': []}
                elif line[:1] == b'\n':
                    transactions = []
        else:
            raise UserError(_('This file is either not a bank statement or is not correctly formed.'))

        vals_bank_statement.update({
            'balance_end_real': total,
            'transactions': transactions
        })
        return None, None, [vals_bank_statement]
DATE_OF_TRANSACTION = b'D'
TOTAL_AMOUNT = b'T'
CHECK_NUMBER = b'N'
PAYEE = b'P'
MEMO = b'M'
END_OF_ITEM = b'^'
