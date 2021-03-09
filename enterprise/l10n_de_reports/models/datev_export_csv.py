# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import pycompat
from odoo.exceptions import UserError

from datetime import datetime
import json
import zipfile
import time
import io

class AccountDatevCompany(models.Model):
    _inherit = 'res.company'

    # Adding the fields as company_dependent does not break stable policy
    l10n_de_datev_consultant_number = fields.Char(company_dependent=True)
    l10n_de_datev_client_number = fields.Char(company_dependent=True)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_de_datev_identifier = fields.Integer(string='Datev Identifier',
        copy=False, tracking=True,
        help="The Datev identifier is a unique identifier for exchange with the government. "
             "If you had previous exports with another identifier, you can put it here. "
             "If it is 0, then it will take the database id + the value in the system parameter "
             "l10n_de.datev_start_count. ")

    @api.constrains('l10n_de_datev_identifier')
    def _check_datev_identifier(self):
        for partner in self.filtered(lambda p: p.l10n_de_datev_identifier != 0):
            if self.search([('id', '!=', partner.id),
                            ('l10n_de_datev_identifier', '=', partner.l10n_de_datev_identifier)], limit=1):
                raise UserError(_('You have already defined a partner with the same Datev identifier. '))


class AccountMoveL10NDe(models.Model):
    _inherit = 'account.move'

    l10n_de_datev_main_account_id = fields.Many2one('account.account', compute='_get_datev_account',
        help='Technical field needed for datev export', store=True)

    @api.depends('journal_id', 'line_ids', 'journal_id.default_debit_account_id', 'journal_id.default_credit_account_id')
    def _get_datev_account(self):
        for move in self:
            move.l10n_de_datev_main_account_id = value = False
            # If move has an invoice, return invoice's account_id
            if move.is_invoice(include_receipts=True):
                payment_term_lines = move.line_ids.filtered(
                    lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
                if payment_term_lines:
                    move.l10n_de_datev_main_account_id = payment_term_lines[0].account_id
                continue
            # If move belongs to a bank journal, return the journal's account (debit/credit should normally be the same)
            if move.journal_id.type == 'bank' and move.journal_id.default_debit_account_id:
                move.l10n_de_datev_main_account_id = move.journal_id.default_debit_account_id
                continue
            # If the move is an automatic exchange rate entry, take the gain/loss account set on the exchange journal
            elif move.journal_id.type == 'general' and move.journal_id == self.env.company.currency_exchange_journal_id:
                accounts = [
                    move.journal_id.default_debit_account_id,
                    move.journal_id.default_credit_account_id,
                ]
                lines = move.line_ids.filtered(lambda r: r.account_id in accounts)
                if len(lines) == 1:
                    move.l10n_de_datev_main_account_id = lines.account_id
                    continue

            # Look for an account used a single time in the move, that has no originator tax
            aml_debit = self.env['account.move.line']
            aml_credit = self.env['account.move.line']
            for aml in move.line_ids:
                if aml.debit > 0:
                    aml_debit += aml
                if aml.credit > 0:
                    aml_credit += aml
            if len(aml_debit) == 1:
                value = aml_debit[0].account_id
            elif len(aml_credit) == 1:
                value = aml_credit[0].account_id
            else:
                aml_debit_wo_tax = [a for a in aml_debit if not a.tax_line_id]
                aml_credit_wo_tax = [a for a in aml_credit if not a.tax_line_id]
                if len(aml_debit_wo_tax) == 1:
                    value = aml_debit_wo_tax[0].account_id
                elif len(aml_credit_wo_tax) == 1:
                    value = aml_credit_wo_tax[0].account_id
            move.l10n_de_datev_main_account_id = value


class DatevExportCSV(models.AbstractModel):
    _inherit = 'account.general.ledger'

    def _get_reports_buttons(self):
        buttons = super(DatevExportCSV, self)._get_reports_buttons()
        buttons += [{'name': _('Export Datev (zip)'), 'sequence': 3, 'action': 'print_zip', 'file_export_type': _('Datev zip')}]
        return buttons

    # This will be removed in master as export CSV is not needed anymore
    # Can't remove it in version 11 in order to not break the stable policy
    def print_csv(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'csv',
            }
        }

    def print_zip(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {'model': self.env.context.get('model'),
                     'options': json.dumps(options),
                     'output_format': 'zip',
                     }
        }

    def get_zip(self, options):
        # Check ir_attachment for method _get_path
        # create a sha and replace 2 first letters by something not hexadecimal
        # Return full_path as 2nd args, use it as name for Zipfile
        # Don't need to unlink as it will be done automatically by bgarbage collector
        # of attachment cron
        # This create a zip file that we store as an ir_attachment. To prevent overwritting
        # an existing ir_attachement, we store it in a folder called ww (all others attachments
        # are inside folders that only has hexadecimal value as name)
        # This is done so that we can send the zip directly to client without putting it
        # in memory. After having created the file, we also have to call _file_delete
        # Otherwise the folder ww won't be garbage collected by the cron
        ir_attachment = self.env['ir.attachment']
        sha = ir_attachment._compute_checksum(str(time.time()).encode('utf-8'))
        fname, full_path = ir_attachment._get_path(False, 'ww' + sha[2:])
        with zipfile.ZipFile(full_path, 'w', False) as zf:
            zf.writestr('EXTF_accounting_entries.csv', self.get_csv(options))
            zf.writestr('EXTF_customer_accounts.csv', self._get_partner_list(options))
        ir_attachment._file_delete(fname)
        return open(full_path, 'rb')

    def _get_datev_client_number(self):
        consultant_number = self.env.company.l10n_de_datev_consultant_number
        client_number = self.env.company.l10n_de_datev_client_number
        if not consultant_number:
            consultant_number = 99999
        if not client_number:
            client_number = 999
        return [consultant_number, client_number]

    def _get_partner_list(self, options):
        date_from = fields.Date.from_string(options.get('date').get('date_from'))
        date_to = fields.Date.from_string(options.get('date').get('date_to'))
        fy = self.env.company.compute_fiscalyear_dates(date_to)

        date_from = datetime.strftime(date_from, '%Y%m%d')
        date_to = datetime.strftime(date_to, '%Y%m%d')
        fy = datetime.strftime(fy.get('date_from'), '%Y%m%d')
        datev_info = self._get_datev_client_number()

        output = io.BytesIO()
        writer = pycompat.csv_writer(output, delimiter=';', quotechar='"', quoting=2)

        preheader = ['EXTF', 510, 16, 'Debitoren/Kreditoren', 4, None, None, '', '', '', datev_info[0], datev_info[1], fy, 8,
            '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
        header = ['Konto', 'Name (AdressatentypUnternehmen)', 'Name (Adressatentypnatürl. Person)', '', '', '', 'Adressatentyp']
        move_line_ids = self.with_context(self._set_context(options), print_mode=True, aml_only=True)._get_lines(options)
        lines = [preheader, header]

        if len(move_line_ids):
            self.env.cr.execute("""
                SELECT distinct(aml.partner_id)
                FROM account_move_line aml
                LEFT JOIN account_move m
                    ON aml.move_id = m.id
                WHERE aml.id IN %s
                    AND aml.tax_line_id IS NULL
                    AND aml.debit != aml.credit
                    AND aml.account_id != m.l10n_de_datev_main_account_id""", (tuple(move_line_ids),))
        partners = self.env['res.partner'].browse([p.get('partner_id') for p in self.env.cr.dictfetchall()])
        for partner in partners:
            code = self._find_partner_account(partner.property_account_receivable_id, partner)
            line_value = {
                'code': code,
                'company_name': partner.name if partner.is_company else '',
                'person_name': '' if partner.is_company else partner.name,
                'natural': partner.is_company and '2' or '1'
            }
            # Idiotic program needs to have a line with 243 elements ordered in a given fashion as it
            # does not take into account the header and non mandatory fields
            array = ['' for x in range(243)]
            array[0] = line_value.get('code')
            array[1] = line_value.get('company_name')
            array[2] = line_value.get('person_name')
            array[6] = line_value.get('natural')
            lines.append(array)
            code_payable = self._find_partner_account(partner.property_account_payable_id, partner)
            if code_payable != code:
                line_value['code'] = code_payable
                array[0] = line_value.get('code')
                lines.append(array)
        writer.writerows(lines)
        return output.getvalue()

    def _find_partner_account(self, account, partner):
        if (account.internal_type in ('receivable', 'payable') and partner):
            # Check if we have a property as receivable/payable on the partner
            # We use the property because in datev and in germany, partner can be of 2 types
            # important partner which have a specific account number or a virtual partner
            # Which has only a number. To differentiate between the two, if a partner in Odoo
            # explicitely has a receivable/payable account set, we use that account, otherwise
            # we assume it is not an important partner and his datev virtual id will be the
            # l10n_de_datev_identifier set or the id + the start count parameter.
            account = account.internal_type == 'receivable' and partner.property_account_receivable_id or partner.property_account_payable_id
            prop = self.env['ir.property'].search([
                ('name', '=', account.internal_type == 'receivable' and 'property_account_receivable_id' or 'property_account_payable_id'),
                ('res_id', '=', 'res.partner,' + str(partner.id)),
                ('value_reference', '=', 'account.account,'+str(account.id))
            ])
            if prop:
                return str(account.code).ljust(8, '0')
            param_start = self.env['ir.config_parameter'].sudo().get_param('l10n_de.datev_start_count')
            start_count = param_start and param_start.isdigit() and int(param_start) or 100000000
            return partner.l10n_de_datev_identifier or start_count + partner.id
        return str(account.code).ljust(8, '0')

    # Source: http://www.datev.de/dnlexom/client/app/index.html#/document/1036228/D103622800029
    def get_csv(self, options):
        # last 2 element of preheader should be filled by "consultant number" and "client number"
        date_from = fields.Date.from_string(options.get('date').get('date_from'))
        date_to = fields.Date.from_string(options.get('date').get('date_to'))
        fy = self.env.company.compute_fiscalyear_dates(date_to)

        date_from = datetime.strftime(date_from, '%Y%m%d')
        date_to = datetime.strftime(date_to, '%Y%m%d')
        fy = datetime.strftime(fy.get('date_from'), '%Y%m%d')
        datev_info = self._get_datev_client_number()

        output = io.BytesIO()
        writer = pycompat.csv_writer(output, delimiter=';', quotechar='"', quoting=2)
        preheader = ['EXTF', 510, 21, 'Buchungsstapel', 7, '', '', '', '', '', datev_info[0], datev_info[1], fy, 8,
            date_from, date_to, '', '', '', '', 0, 'EUR', '', '', '', '', '', '', '', '', '']
        header = ['Umsatz (ohne Soll/Haben-Kz)', 'Soll/Haben-Kennzeichen', 'WKZ Umsatz', 'Kurs', 'Basis-Umsatz', 'WKZ Basis-Umsatz', 'Konto', 'Gegenkonto (ohne BU-Schlüssel)', 'BU-Schlüssel', 'Belegdatum', 'Belegfeld 1', 'Belegfeld 2', 'Skonto', 'Buchungstext']

        move_line_ids = self.with_context(self._set_context(options), print_mode=True, aml_only=True)._get_lines(options)
        lines = [preheader, header]

        moves = move_line_ids
        # find all account_move
        if len(move_line_ids):
            self.env.cr.execute("""SELECT distinct(move_id) FROM account_move_line WHERE id IN %s""", (tuple(move_line_ids),))
            move_ids = [l.get('move_id') for l in self.env.cr.dictfetchall()]
            moves = self.env['account.move'].browse(move_ids)
        for m in moves:
            # Account-counterAccount-amount-partner
            move_line_set = {}
            for aml in m.line_ids:
                if aml.debit == aml.credit:
                    # Ignore debit = credit = 0
                    continue
                # If both account and counteraccount are the same, ignore the line
                if aml.account_id == aml.move_id.l10n_de_datev_main_account_id:
                    continue
                # If line is a tax ignore it as datev requires single line with gross amount and deduct tax itself based
                # on account or on the control key code
                if aml.tax_line_id:
                    continue

                amount = abs(aml.balance)
                # Finding back the amount with tax included from the move can be tricky
                # The line with the tax contains the tax_base_amount which is the gross value
                # However if we have 2 product lines with the same tax, we will have a move like this
                # Debit   Credit   Tax_line_id   Tax_ids   Tax_base_amount   Account_id
                #  10        0        false       false            0          Receivable
                #  0         3         1          false            7          Tax
                #  0        3,5       false        [1]             0          Income Account
                #  0        3,5       false        [1]             0          Income Account
                #
                # What we want to export for his move in datev is something like this:
                # Account             CounterAccount   Amount
                # Income Account      Receivable        10
                #
                # So when we are on an "Income Account" line linked to a tax, we try to find back
                # the line representing the tax and we use as amount the tax line balance + base_amount
                # This means that in the case we happen to have another line with same tax and income account,
                # (as described above), We have to skip it.
                # A Problem that might happen since tax are grouped is: if we have a line
                # with tax 1 and 2 specified on the line, and another line with only tax 1
                # specified on the line. This will result in a case where we can't easily get
                # back the gross amount for both lines. This case is not supported by this export
                # function and will result in incorrect exported lines for datev.
                code_correction = ''
                if aml.balance > 0:
                    letter = 's'
                elif aml.balance < 0:
                    letter = 'h'
                else:
                    if aml.move_id.type in ('out_invoice', 'in_refund',):
                        letter = 'h'
                    else:
                        letter = 's'
                if aml.tax_ids:
                    amount = 0
                    tax_balance_sum = 0
                    for tax in aml.tax_ids:
                        # Find tax line in the move and get it's tax_base_amount
                        if tax.amount:
                            tax_line = m.line_ids.filtered(lambda l: l.tax_line_id == tax and l.partner_id == aml.partner_id)
                            amount += abs(sum(tax_line.mapped('balance'))) + abs(sum(tax_line.mapped('tax_base_amount')))
                            tax_balance_sum += sum(tax_line.mapped('balance'))
                        else:
                            # 0% tax leave no tax_ids so find manually all lines with such tax
                            tax_line = m.line_ids.filtered(lambda l: tax in l.tax_ids and l.partner_id == aml.partner_id)
                            amount += abs(sum(tax_line.mapped('balance')))
                    if tax_balance_sum > 0:
                        letter = 's'
                    elif tax_balance_sum < 0:
                        letter = 'h'
                    else:
                        if aml.move_id.type in ('out_invoice', 'in_refund',):
                            letter = 'h'
                        else:
                            letter = 's'

                # account and counterpart account
                to_account_code = self._find_partner_account(aml.move_id.l10n_de_datev_main_account_id, aml.partner_id)
                account_code = u'{code}'.format(code=self._find_partner_account(aml.account_id, aml.partner_id))
                if not aml.account_id.tax_ids and aml.tax_ids:
                    # Take the correction code from the tax
                    code_correction = aml.tax_ids[0].l10n_de_datev_code

                # If line is already to be add from this move, skip it
                match_key = '%s-%s-%s-%s' % (account_code, to_account_code, amount, aml.partner_id)
                if (move_line_set.get(match_key)):
                    continue
                else:
                    move_line_set[match_key] = True
                # reference
                receipt1 = aml.move_id.name
                if aml.move_id.journal_id.type == 'purchase' and aml.move_id.ref:
                    receipt1 = aml.move_id.ref

                # on receivable/payable aml of sales/purchases
                receipt2 = ''
                if to_account_code == account_code and aml.date_maturity:
                    receipt2 = aml.date

                currency = aml.company_id.currency_id
                partner_vat = aml.tax_ids and aml.move_id.partner_id.vat or ''
                line_value = {
                    'waehrung': currency.name,
                    'sollhaben': letter,
                    'amount': str(amount).replace('.', ','),
                    'buschluessel': code_correction,
                    'gegenkonto': to_account_code,
                    'belegfeld1': receipt1[-12:],
                    'belegfeld2': receipt2,
                    'datum': aml.move_id.date,
                    'konto': account_code or '',
                    'kurs': str(currency.rate).replace('.', ','),
                    'buchungstext': receipt1,
                }
                # Idiotic program needs to have a line with 116 elements ordered in a given fashion as it
                # does not take into account the header and non mandatory fields
                array = ['' for x in range(116)]
                array[0] = line_value.get('amount')
                array[1] = line_value.get('sollhaben')
                array[2] = line_value.get('waehrung')
                array[6] = line_value.get('konto')
                array[7] = line_value.get('gegenkonto')
                array[8] = line_value.get('buschluessel')
                array[9] = line_value.get('datum')
                array[10] = line_value.get('belegfeld1')
                array[11] = line_value.get('belegfeld2')
                array[13] = line_value.get('buchungstext')
                lines.append(array)
        writer.writerows(lines)
        return output.getvalue()


class report_account_coa(models.AbstractModel):
    _inherit = "account.coa.report"

    def _get_reports_buttons(self):
        buttons = super(report_account_coa, self)._get_reports_buttons()
        # It doesn't make sense to print the DATEV on anything else than the
        # proper general ledger
        return [b for b in buttons if b.get('action') != 'print_zip']
