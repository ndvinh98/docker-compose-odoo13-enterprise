# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
import itertools
import io
import logging
import os
import zipfile
import re
from datetime import datetime, timedelta

from os import listdir
from os.path import isfile, join

from odoo import models, fields, tools, _
from odoo.exceptions import UserError, RedirectWarning

_logger = logging.getLogger(__name__)

try:
    from dbfread import DBF
except ImportError:
    DBF = None
    _logger.warning('dbfread library not found, Winbooks Import features disabled. If you plan to use it, please install the dbfread library from https://pypi.org/project/dbfread/')


class WinbooksImportWizard(models.TransientModel):
    _name = "account.winbooks.import.wizard"
    _description = 'Account Winbooks import wizard'

    zip_file = fields.Binary('File', required=True)
    only_open = fields.Boolean('Import only open years', help="Years closed in Winbooks are likely to have incomplete data. The counter part of incomplete entries will be set in a suspense account", default=True)
    suspense_code = fields.Char(string="Suspense Account Code", help="This is the code of the account in which you want to put the counterpart of unbalanced moves. This might be an account from your Winbooks data, or an account that you created in Odoo before the import.")

    def import_partner_info(self, file_dir, files):
        """Import information related to partner from *_table*.dbf files.
        The data in those files is the title, language, payment term and partner
        category.
        :return: (civility_data, category_data)
            civility_data is a dictionary whose keys are the Winbooks references
                and the values the civility title
            category_data is a dictionary whose keys are the Winbooks category
                references and the values the partner categories
        """
        _logger.info("Import Partner Infos")
        civility_data = {}
        category_data = {}
        ResPartnerTitle = self.env['res.partner.title']
        ResPartnerCategory = self.env['res.partner.category']
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                if rec.get('TTYPE') == 'CIVILITY':
                    shortcut = rec.get('TID')
                    title = ResPartnerTitle.search([('shortcut', '=', shortcut)], limit=1)
                    if not title:
                        title = ResPartnerTitle.create({'shortcut': shortcut, 'name': rec.get('TDESC')})
                    civility_data[shortcut] = title.id
                elif rec.get('TTYPE').startswith('CAT'):
                    category = ResPartnerCategory.search([('name', '=', rec.get('TDESC'))], limit=1)
                    if not category:
                        category = ResPartnerCategory.create({'name': rec.get('TDESC')})
                    category_data[rec.get('TID')] = category.id
        return civility_data, category_data

    def import_partner(self, file_dir, files, civility_data, category_data, account_data):
        """Import partners from *_csf*.dbf files.
        The data in those files is the partner details, its type, its category,
        bank informations, and central accounts.
        :return: a dictionary whose keys are the Winbooks partner references and
            the values are the partner ids in Odoo.
        """
        _logger.info("Import Partners")
        partner_data = {}
        ResBank = self.env['res.bank']
        ResCountry = self.env['res.country']
        ResPartner = self.env['res.partner']
        ResPartnerBank = self.env['res.partner.bank']
        partner_data_dict = {}
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                if not rec.get('NUMBER'):
                    continue
                partner = ResPartner.search([('ref', '=', rec.get('NUMBER'))], limit=1)
                if partner:
                    partner_data[rec.get('NUMBER')] = partner.id
                if not partner:
                    vatcode = rec.get('VATNUMBER') and rec.get('COUNTRY') and (rec.get('COUNTRY') + rec.get('VATNUMBER').replace('.', ''))
                    if not rec.get('VATNUMBER') or not rec.get('COUNTRY') or not ResPartner.simple_vat_check(rec.get('COUNTRY').lower(), vatcode):
                        vatcode = ''
                    data = {
                        'ref': rec.get('NUMBER'),
                        'name': rec.get('NAME1'),
                        'street': rec.get('ADRESS1'),
                        'country_id': ResCountry.search([('code', '=', rec.get('COUNTRY'))], limit=1).id,
                        'city': rec.get('CITY'),
                        'street2': rec.get('ADRESS2'),
                        'vat': vatcode,
                        'phone': rec.get('TELNUMBER'),
                        'zip': rec.get('ZIPCODE') and ''.join([n for n in rec.get('ZIPCODE') if n.isdigit()]),
                        'email': rec.get('EMAIL'),
                        'active': not rec.get('ISLOCKED'),
                        'title': civility_data.get(rec.get('CIVNAME1'), False),
                        'category_id': [(6, 0, [category_data.get(rec.get('CATEGORY'))])] if category_data.get(rec.get('CATEGORY')) else False
                    }
                    if partner_data_dict.get(rec.get('IBANAUTO') or 'num' + rec.get('NUMBER')):
                        for key, value in partner_data_dict[rec.get('IBANAUTO') or 'num' + rec.get('NUMBER')].items():
                            if value:  # Winbooks has different partners for customer/supplier. Here we merge the data of the 2
                                data[key] = value
                    if rec.get('NAME2'):
                        data.update({
                            'child_ids': [(0, 0, {'name': rec.get('NAME2'), 'title': civility_data.get(rec.get('CIVNAME2'), False)})]
                        })
                    # manage the bank account of the partner
                    if rec.get('IBANAUTO'):
                        partner_bank = ResPartnerBank.search([('acc_number', '=', rec.get('IBANAUTO'))], limit=1)
                        if partner_bank:
                            data['bank_ids'] = [(4, partner_bank.id)]
                        else:
                            bank = ResBank.search([('name', '=', rec.get('BICAUTO'))], limit=1)
                            if not bank:
                                bank = ResBank.create({'name': rec.get('BICAUTO')})
                            data.update({
                                'bank_ids': [(0, 0, {
                                    'acc_number': rec.get('IBANAUTO'),
                                    'bank_id': bank.id
                                })],
                            })
                    # manage the default payable/receivable accounts for the partner
                    if rec.get('CENTRAL'):
                        if rec.get('TYPE') == '1':
                            data['property_account_receivable_id'] = account_data[rec.get('CENTRAL')]
                        else:
                            data['property_account_payable_id'] = account_data[rec.get('CENTRAL')]

                    partner_data_dict[rec.get('IBANAUTO') or 'num' + rec.get('NUMBER')] = data
                    if len(partner_data_dict) % 100 == 0:
                        _logger.info("Advancement: {}".format(len(partner_data_dict)))

        partner_ids = ResPartner.create(partner_data_dict.values())
        for partner in partner_ids:
            partner_data[partner.ref] = partner.id
        return partner_data

    def import_account(self, file_dir, files, journal_data):
        """Import accounts from *_acf*.dbf files.
        The data in those files are the type, name, code and currency of the
        account as well as wether it is used as a default central account for
        partners or taxes.
        :return: (account_data, account_central, account_deprecated_ids, account_tax)
            account_data is a dictionary whose keys are the Winbooks account
                references and the values are the account ids in Odoo.
            account_central is a dictionary whose keys are the Winbooks central
                account references and the values are the account ids in Odoo.
            account_deprecated_ids is a recordset of account that need to be
                deprecated after the import.
            account_tax is a dictionary whose keys are the Winbooks account
                references and the values are the Winbooks tax references.
        """
        def manage_centralid(account, centralid):
            "Set account to being a central account"
            property_name = None
            account_central[centralid] = account.id
            if centralid == 'S1':
                property_name = 'property_account_payable_id'
                model_name = 'res.partner'
            if centralid == 'C1':
                property_name = 'property_account_receivable_id'
                model_name = 'res.partner'
            if centralid == 'V01':
                property_name = 'property_tax_receivable_account_id'
                model_name = 'account.tax.group'
            if centralid == 'V03':
                property_name = 'property_tax_payable_account_id'
                model_name = 'account.tax.group'
            if property_name:
                field_id = self.env['ir.model.fields'].search([('model', '=', model_name), ('name', '=', property_name)], limit=1)
                self.env['ir.property'].create({'name': property_name, 'company_id': self.env.company.id, 'fields_id': field_id.id, 'value_reference': 'account.account,{}'.format(account.id)})

        _logger.info("Import Accounts")
        account_data = {}
        account_central = {}
        account_tax = {}
        recs = []
        grouped = collections.defaultdict(list)
        AccountAccount = self.env['account.account']
        ResCurrency = self.env['res.currency']
        AccountGroup = self.env['account.group']
        account_types = [
            {'min': 100, 'max': 160, 'id': 'account.data_account_type_equity'},
            {'min': 160, 'max': 200, 'id': 'account.data_account_type_non_current_liabilities'},
            {'min': 200, 'max': 280, 'id': 'account.data_account_type_non_current_assets'},
            {'min': 280, 'max': 290, 'id': 'account.data_account_type_fixed_assets'},
            {'min': 290, 'max': 400, 'id': 'account.data_account_type_current_assets'},
            {'min': 400, 'max': 401, 'id': 'account.data_account_type_receivable', 'reconcile': True},
            {'min': 401, 'max': 420, 'id': 'account.data_account_type_current_assets'},
            {'min': 420, 'max': 440, 'id': 'account.data_account_type_current_liabilities'},
            {'min': 440, 'max': 441, 'id': 'account.data_account_type_payable', 'reconcile': True},
            {'min': 441, 'max': 490, 'id': 'account.data_account_type_current_liabilities'},
            {'min': 490, 'max': 492, 'id': 'account.data_account_type_current_assets'},
            {'min': 492, 'max': 500, 'id': 'account.data_account_type_current_liabilities'},
            {'min': 500, 'max': 600, 'id': 'account.data_account_type_liquidity'},
            {'min': 600, 'max': 700, 'id': 'account.data_account_type_expenses'},
            {'min': 700, 'max': 822, 'id': 'account.data_account_type_revenue'},
            {'min': 822, 'max': 860, 'id': 'account.data_account_type_expenses'},
        ]
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                recs.append(rec)
        for item in recs:
            grouped[item.get('TYPE')].append(item)
        rec_number_list = []
        account_data_list = []
        journal_centered_list = []
        is_deprecated_list = []
        account_deprecated_ids = self.env['account.account']
        for key, val in grouped.items():
            if key == '3':  # 3=general account, 9=title account
                for rec in val:
                    account = AccountAccount.search(
                        [('code', '=', rec.get('NUMBER')), ('company_id', '=', self.env.company.id)], limit=1)
                    if account:
                        account_data[rec.get('NUMBER')] = account.id
                        rec['CENTRALID'] and manage_centralid(account, rec['CENTRALID'])
                    if not account and rec.get('NUMBER') not in rec_number_list:
                        data = {
                            'code': rec.get('NUMBER'),
                            'name': rec.get('NAME11'),
                            'group_id': AccountGroup.search([('code_prefix', '=', rec.get('CATEGORY'))], limit=1).id,
                            'currency_id': ResCurrency.search([('name', '=', rec.get('CURRENCY'))], limit=1).id
                        }
                        if rec.get('VATCODE'):
                            account_tax[rec.get('NUMBER')] = rec.get('VATCODE')
                        try:
                            account_code = int(rec.get('NUMBER')[:3])
                        except Exception:
                            _logger.warning(_('%s is not a valid account number for %s.') % (rec.get('NUMBER'), rec.get('NAME11')))
                            account_code = 300  # set Current Asset by default for deprecated accounts
                        for account_type in account_types:
                            if account_code in range(account_type['min'], account_type['max']):
                                data.update({
                                    'user_type_id': self.env.ref(account_type['id']).id,
                                    'reconcile': account_type.get('reconcile', False)
                                })
                                break
                        # fallback for accounts not in range(100000,860000)
                        if not data.get('user_type_id'):
                            data['user_type_id'] = self.env.ref('account.data_account_type_other_income').id
                        account_data_list.append(data)
                        rec_number_list.append(rec.get('NUMBER'))
                        journal_centered_list.append(rec.get('CENTRALID'))
                        is_deprecated_list.append(rec.get('ISLOCKED'))

                        if len(account_data_list) % 100 == 0:
                            _logger.info("Advancement: {}".format(len(account_data_list)))
        account_ids = AccountAccount.create(account_data_list)
        for account, rec_number, journal_centred, is_deprecated in zip(account_ids, rec_number_list, journal_centered_list, is_deprecated_list):
            account_data[rec_number] = account.id
            # create the ir.property if this is marked as a default account for something
            journal_centred and manage_centralid(account, journal_centred)
            # we can't deprecate the account now as we still need to add lines with this account
            # keep the list in memory so that we can deprecate later
            if is_deprecated:
                account_deprecated_ids += account
        return account_data, account_central, account_deprecated_ids, account_tax

    def post_process_account(self, account_data, vatcode_data, account_tax):
        """Post process the accounts after the taxes creation to add the taxes
        on the accounts"""
        for account, vat in account_tax.items():
            if vat in vatcode_data:
                self.env['account.account'].browse(account_data[account]).write({'tax_ids': [(4, vatcode_data[vat])]})

    def import_journal(self, file_dir, files):
        """Import journals from *_dbk*.dbf files.
        The data in those files are the name, code and type of the journal.
        :return: a dictionary whose keys are the Winbooks journal references and
            the values the journal ids in Odoo
        """
        _logger.info("Import Journals")
        journal_types = {
            '0': 'purchase',
            '1': 'purchase',
            '2': 'sale',
            '3': 'sale',
            '5': 'general',
        }
        journal_data = {}
        AccountJournal = self.env['account.journal']
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                if not rec.get('DBKID'):
                    continue
                journal = AccountJournal.search(
                    [('code', '=', rec.get('DBKID')), ('company_id', '=', self.env.company.id)], limit=1)
                if not journal:
                    if rec.get('DBKTYPE') == '4':
                        journal_type = 'bank' if 'IBAN' in rec.get('DBKOPT') else 'cash'
                    else:
                        journal_type = journal_types.get(rec.get('DBKTYPE'), 'general')
                    data = {
                        'name': rec.get('DBKDESC'),
                        'code': rec.get('DBKID'),
                        'type': journal_type,
                    }
                    journal = AccountJournal.create(data)
                journal_data[rec.get('DBKID')] = journal.id
        return journal_data

    def find_file(self, name, path):
        attachments = []
        for root, dirs, files in os.walk(path):
            for file_name in files:
                if name in file_name and '.xml' not in file_name.lower():
                    attachments.append(os.path.join(root, file_name))
        return attachments

    def import_move(self, file_dir, files, scanfiles, account_data, journal_data, partner_data, vatcode_data, param_data):
        _logger.warning("`import_move` is deprecated, use `_import_move` instead")
        self._import_move(file_dir, files, scanfiles, account_data, {}, journal_data, partner_data, vatcode_data, param_data)

    def _import_move(self, file_dir, files, scanfiles, account_data, account_central, journal_data, partner_data, vatcode_data, param_data):
        """Import the journal entries from *_act*.dfb and @scandbk.zip files.
        The data in *_act*.dfb files are related to the moves and the data in
        @scandbk.zip files are the attachments.
        """
        _logger.info("Import Moves")
        recs = []
        ResCurrency = self.env['res.currency']
        IrAttachment = self.env['ir.attachment']
        suspense_account = self.env['account.account'].search([('code', '=', self.suspense_code)], limit=1)
        if not self.only_open and not suspense_account:
            raise UserError(_("The code for the Suspense Account you entered doesn't match any account"))
        counter_part_created = False
        for file_name in scanfiles:
            with zipfile.ZipFile(join(file_dir, file_name), 'r') as scan_zip:
                scan_zip.extractall(file_dir)
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                if rec.get('BOOKYEAR') and rec.get('DOCNUMBER') != '99999999':
                    recs.append(rec)
        result = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in recs)]
        grouped = collections.defaultdict(list)
        for item in result:
            # Group by number/year/period
            grouped[item['DOCNUMBER'], item['DBKCODE'], item['DBKTYPE'], item['BOOKYEAR'], item['PERIOD']] += [item]

        move_data_list = []
        pdf_file_list = []
        reconcile_number_set = set()
        for key, val in grouped.items():
            journal_id = self.env['account.journal'].browse(journal_data.get(key[1]))
            bookyear = int(key[3], 36)
            if not bookyear or (self.only_open and bookyear not in param_data['openyears']):
                continue
            perdiod_number = len(param_data['period_date'][bookyear]) - 2
            period = min(int(key[4]), perdiod_number + 1)  # closing is 99 in winbooks, not 13
            start_period_date = param_data['period_date'][bookyear][period]
            if 1 <= period < perdiod_number:
                end_period_date = param_data['period_date'][bookyear][period + 1] + timedelta(days=-1)
            elif period == perdiod_number:  # take the last day of the year = day of closing
                end_period_date = param_data['period_date'][bookyear][period + 1]
            else:  # opening (0) or closing (99) are at a fixed date
                end_period_date = start_period_date
            move_date = val[0].get('DATEDOC')
            move_data_dict = {
                'journal_id': journal_id.id,
                'type': 'out_invoice' if journal_id.type == 'sale' else 'in_invoice' if journal_id.type == 'purchase' else 'entry',
                'ref': '%s_%s' % (key[1], key[0]),
                'company_id': self.env.company.id,
                'date': min(max(start_period_date, move_date), end_period_date),
            }
            if not move_data_dict.get('journal_id') and key[1] == 'MATCHG':
                continue
            move_line_data_list = []
            move_amount_total = 0
            move_total_receivable_payable = 0

            # Split lines having a different sign on the balance in company currency and foreign currency
            tmp_val = []
            for rec in val:
                tmp_val += [rec]
                if rec['AMOUNTEUR'] * (rec['CURRAMOUNT'] or 0) < 0:
                    tmp_val[-1]['CURRAMOUNT'] = 0
                    tmp_val += [rec.copy()]
                    tmp_val[-1]['AMOUNTEUR'] = 0
            val = tmp_val

            # Basic line info
            for rec in val:
                currency = ResCurrency.search([('name', '=', rec.get('CURRCODE'))], limit=1)
                if currency == self.env.company.currency_id:
                    currency = self.env['res.currency']
                partner_id = self.env['res.partner'].browse(partner_data.get(rec.get('ACCOUNTRP'), False))
                account_id = self.env['account.account'].browse(account_data.get(rec.get('ACCOUNTGL')))
                matching_number = rec.get('MATCHNO') and '%s-%s' % (rec.get('ACCOUNTGL'), rec.get('MATCHNO')) or False
                line_data = {
                    'date': rec.get('DATE', False),
                    'account_id': account_id.id,
                    'partner_id': partner_id.id,
                    'date_maturity': rec.get('DUEDATE', False),
                    'name': rec.get('COMMENT'),
                    'currency_id': currency.id,
                    'debit': rec.get('AMOUNTEUR') if rec.get('AMOUNTEUR') and rec.get('AMOUNTEUR') >= 0 else 0.0,
                    'credit': abs(rec.get('AMOUNTEUR')) if rec.get('AMOUNTEUR') and rec.get('AMOUNTEUR') < 0 else 0.0,
                    'amount_currency': rec.get('CURRAMOUNT') if currency and rec.get('CURRAMOUNT') else 0.0,
                    'amount_residual_currency': rec.get('CURRAMOUNT') if currency and rec.get('CURRAMOUNT') else 0.0,
                    'winbooks_matching_number': matching_number,
                    'exclude_from_invoice_tab': rec.get('DOCORDER') == 'VAT' or (account_id.user_type_id.type in ('receivable', 'payable') and journal_id.type in ('sale', 'purchase')),
                }
                if matching_number:
                    reconcile_number_set.add(matching_number)
                if rec.get('AMOUNTEUR'):
                    move_amount_total = round(move_amount_total, 2) + round(rec.get('AMOUNTEUR'), 2)
                move_line_data_list.append((0, 0, line_data))
                if account_id.user_type_id.type in ('receivable', 'payable'):
                    move_total_receivable_payable += rec.get('AMOUNTEUR')

            # Compute refund value
            if journal_id.type in ('sale', 'purchase'):
                is_refund = move_total_receivable_payable < 0 if journal_id.type == 'sale' else move_total_receivable_payable > 0
            else:
                is_refund = False

            # Add tax information
            for line_data, rec in zip(move_line_data_list, val):
                if self.env['account.account'].browse(account_data.get(rec.get('ACCOUNTGL'))).user_type_id.type in ('receivable', 'payable'):
                    continue
                tax_line = self.env['account.tax'].browse(vatcode_data.get(rec.get('VATCODE') or rec.get('VATIMPUT', [])))
                if not tax_line and line_data[2]['account_id'] in account_central.values():
                    # this line is on a centralised account, most likely a tax account, but is not linked to a tax
                    # this is because the counterpart (second repartion line) line of a tax is not flagged in Winbooks
                    try:
                        counterpart = next(r for r in val if r['AMOUNTEUR'] == -rec['AMOUNTEUR'] and r['DOCORDER'] == 'VAT' and r['VATCODE'])
                        tax_line = self.env['account.tax'].browse(vatcode_data.get(counterpart['VATCODE']))
                    except StopIteration:
                        pass  # We didn't find a tax line that is counterpart with same amount
                repartition_line = is_refund and tax_line.refund_repartition_line_ids or tax_line.invoice_repartition_line_ids
                repartition_type = 'tax' if rec.get('DOCORDER') == 'VAT' else 'base'
                line_data[2].update({
                    'tax_ids': tax_line and rec.get('DOCORDER') != 'VAT' and [(4, tax_line.id)] or [],
                    'tag_ids': [(6, 0, tax_line.get_tax_tags(is_refund, repartition_type).ids)],
                    'tax_repartition_line_id': rec.get('DOCORDER') == 'VAT' and repartition_line.filtered(lambda x: x.repartition_type == repartition_type and x.account_id.id == line_data[2]['account_id']).id or False,
                })
            move_line_data_list = [i for i in move_line_data_list if i[2]['account_id'] or i[2]['debit'] or i[2]['credit']]  # Remove empty lines

            # Adapt invoice specific informations
            if move_data_dict['type'] != 'entry':
                move_data_dict['partner_id'] = move_line_data_list[0][2]['partner_id']
                move_data_dict['invoice_date_due'] = move_line_data_list[0][2]['date_maturity']
                move_data_dict['invoice_date'] = move_line_data_list[0][2]['date']
                if is_refund:
                    move_data_dict['type'] = move_data_dict['type'].replace('invoice', 'refund')

            # Balance move, should not happen in an import from a complete db
            if move_amount_total:
                if not counter_part_created:
                    _logger.warning(_('At least one automatic counterpart has been created at import. This is probably an error. Please check entry lines with reference: ') + _('Counterpart (generated at import from Winbooks)'))
                counter_part_created = True
                account_id = journal_id.default_debit_account_id if rec.get('DOCTYPE') in ['0', '1'] else journal_id.default_credit_account_id
                account_id = account_id or (partner_id.property_account_payable_id if rec.get('DOCTYPE') in ['0', '1'] else partner_id.property_account_receivable_id)
                account_id = account_id or suspense_account  # Use suspense account as fallback
                line_data = {
                    'account_id': account_id.id,
                    'date_maturity': rec.get('DUEDATE', False),
                    'name': _('Counterpart (generated at import from Winbooks)'),
                    'credit': move_amount_total if move_amount_total >= 0 else 0.0,
                    'debit': abs(move_amount_total) if move_amount_total < 0 else 0.0,
                }
                move_line_data_list.append((0, 0, line_data))

            # Link all to the move
            move_data_dict['line_ids'] = move_line_data_list
            attachment = '%s_%s_%s' % (key[1], key[4], key[0])
            pdf_file = self.find_file(attachment, file_dir)
            pdf_file_list.append(pdf_file)
            move_data_list.append(move_data_dict)

            if len(move_data_list) % 100 == 0:
                _logger.info("Advancement: {}".format(len(move_data_list)))

        _logger.info("Creating moves")
        move_ids = self.env['account.move'].create(move_data_list)
        _logger.info("Creating attachments")
        for move, pdf_file in zip(move_ids, pdf_file_list):
            if pdf_file:
                attachment_ids = []
                for pdf in pdf_file:
                    attachment_data = {
                        'name': pdf.split('/')[-1],
                        'type': 'binary',
                        'datas': base64.b64encode(open(pdf, "rb").read()),
                        'res_model': move._name,
                        'res_id': move.id,
                        'res_name': move.name
                    }
                    attachment_ids.append(IrAttachment.create(attachment_data))
                move.message_post(attachments=attachment_ids)
        _logger.info("Reconcile")
        for matching_number in reconcile_number_set:
            lines = self.env['account.move.line'].search([('winbooks_matching_number', '=', matching_number), ('reconciled', '=', False)])
            try:
                lines.with_context(no_exchange_difference=True).reconcile()
            except UserError as ue:
                if len(lines.account_id) > 1:
                    _logger.warning('Winbooks matching number {} uses multiple accounts: {}. Lines with that number have not been reconciled in Odoo.'.format(matching_number, ', '.join(lines.mapped('account_id.display_name'))))
                elif not lines.account_id.reconcile:
                    _logger.info("{} {} has reconciled lines, changing the config".format(lines.account_id.code, lines.account_id.name))
                    lines.account_id.reconcile = True
                    lines.with_context(no_exchange_difference=True).reconcile()
                else:
                    raise ue
        return True

    def import_analytic_account(self, file_dir, files):
        """Import the analytic accounts from *_anf*.dbf files.
        :return: a dictionary whose keys are the Winbooks analytic account
        references and the values the analytic account ids in Odoo.
        """
        _logger.info("Import Analytic Accounts")
        analytic_account_data = {}
        AccountAnalyticAccount = self.env['account.analytic.account']
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                if not rec.get('NUMBER'):
                    continue
                analytic_account = AccountAnalyticAccount.search(
                    [('code', '=', rec.get('NUMBER')), ('company_id', '=', self.env.company.id)], limit=1)
                if not analytic_account:
                    data = {
                        'code': rec.get('NUMBER'),
                        'name': rec.get('NAME1'),
                        'active': not rec.get('INVISIBLE')
                    }
                    analytic_account = AccountAnalyticAccount.create(data)
                analytic_account_data[rec.get('NUMBER')] = analytic_account.id
        return analytic_account_data

    def import_analytic_account_line(self, file_dir, files, analytic_account_data, account_data):
        """Import the analytic lines from the *_ant*.dbf files.
        """
        _logger.info("Import Analytic Account Lines")
        analytic_line_data_list = []
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                data = {
                    'date': rec.get('DATE', False),
                    'name': rec.get('COMMENT'),
                    'amount': abs(rec.get('AMOUNTEUR')),
                    'account_id': analytic_account_data.get(rec.get('ZONANA1')),
                    'general_account_id': account_data.get(rec.get('ACCOUNTGL'))
                }
                if data.get('account_id'):
                    analytic_line_data_list.append(data)
                if rec.get('ZONANA2'):
                    new_analytic_line = data.copy()
                    new_analytic_line['account_id'] = analytic_account_data.get(rec.get('ZONANA2'))
                    analytic_line_data_list.append(new_analytic_line)
        self.env['account.analytic.line'].create(analytic_line_data_list)

    def import_vat(self, file_dir, files, account_central):
        """Import the taxes from *codevat.dbf files.
        The data in thos files are the amount, type, including, account and tags
        of the taxes.
        :return: a dictionary whose keys are the Winbooks taxes references and
        the values are the taxes ids in Odoo.
        """
        _logger.info("Import VAT")
        vatcode_data = {}
        treelib = {}
        AccountTax = self.env['account.tax']
        tags_cache = {}

        def get_tags(string):
            "Split the tags, create if it doesn't exist and return m2m command for creation"
            tag_ids = self.env['account.account.tag']
            if not string:
                return tag_ids
            indexes = [i for i, x in enumerate(string) if x in ('+', '-')] + [len(string)]
            for i in range(len(indexes) - 1):
                tag_name = string[indexes[i]: indexes[i + 1]]
                tag_id = tags_cache.get(tag_name, False)
                if not tag_id:
                    tag_id = self.env['account.account.tag'].search([('name', '=', tag_name), ('applicability', '=', 'taxes')])
                    tags_cache[tag_name] = tag_id
                if not tag_id:
                    tag_id = self.env['account.account.tag'].create({'name': tag_name, 'applicability': 'taxes', 'country_id': self.env.company.country_id.id})
                tag_ids += tag_id
            return [(4, id, 0) for id in tag_ids.ids]

        data_list = []
        code_list = []
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                treelib[rec.get('TREELEVEL')] = rec.get('TREELIB1')
                if not rec.get('USRCODE1'):
                    continue
                tax_name = " ".join([treelib[x] for x in [rec.get('TREELEVEL')[:i] for i in range(2, len(rec.get('TREELEVEL')) + 1, 2)]])
                tax = AccountTax.search([('company_id', '=', self.env.company.id), ('name', '=', tax_name),
                                         ('type_tax_use', '=', 'sale' if rec.get('CODE')[0] == '2' else 'purchase')], limit=1)
                if tax.amount != rec.get('RATE') if rec.get('TAXFORM') else 0.0:
                    tax.amount = rec.get('RATE') if rec.get('TAXFORM') else 0.0
                if tax:
                    vatcode_data[rec.get('CODE')] = tax.id
                else:
                    data = {
                        'amount_type': 'percent',
                        'name': tax_name,
                        'company_id': self.env.company.id,
                        'amount': rec.get('RATE') if rec.get('TAXFORM') else 0.0,
                        'type_tax_use': 'sale' if rec.get('CODE')[0] == '2' else 'purchase',
                        'price_include': False if rec.get('TAXFORM') or rec.get('BASFORM') == 'BAL' else True,
                        'refund_repartition_line_ids': [
                            (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0, 'tag_ids': get_tags(rec.get('BASE_CN')), 'company_id': self.env.company.id}),
                            (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'tag_ids': get_tags(rec.get('TAX_CN')), 'company_id': self.env.company.id, 'account_id': account_central.get(rec.get('ACCCN1'), False)}),
                        ],
                        'invoice_repartition_line_ids': [
                            (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0, 'tag_ids': get_tags(rec.get('BASE_INV')), 'company_id': self.env.company.id}),
                            (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'tag_ids': get_tags(rec.get('TAX_INV')), 'company_id': self.env.company.id, 'account_id': account_central.get(rec.get('ACCINV1'), False)}),
                        ],
                    }
                    if rec.get('ACCCN2'):
                        data['refund_repartition_line_ids'] += [(0, 0, {'repartition_type': 'tax', 'factor_percent': -100.0, 'tag_ids': [], 'company_id': self.env.company.id, 'account_id': account_central.get(rec.get('ACCCN2'), False)})]
                    if rec.get('ACCINV2'):
                        data['invoice_repartition_line_ids'] += [(0, 0, {'repartition_type': 'tax', 'factor_percent': -100.0, 'tag_ids': [], 'company_id': self.env.company.id, 'account_id': account_central.get(rec.get('ACCINV2'), False)})]
                    data_list.append(data)
                    code_list.append(rec.get('CODE'))

                    if len(data_list) % 100 == 0:
                        _logger.info("Advancement: {}".format(len(data_list)))
            tax_ids = AccountTax.create(data_list)
            for tax_id, code in zip(tax_ids, code_list):
                vatcode_data[code] = tax_id.id
        return vatcode_data

    def import_param(self, file_dir, files):
        """Import parameters from *_param.dbf files.
        The data in those files is the open or closed state of financial years
        in Winbooks.
        :return: a dictionary with the parameters extracted.
        """
        param_data = {}
        param_data['openyears'] = []
        param_data['period_date'] = {}
        for file_name in files:
            for rec in DBF(join(file_dir, file_name), encoding='latin').records:
                if not rec.get('ID'): continue
                id = rec.get('ID')
                value = rec.get('VALUE')
                # only the lines with status 'open' are known to be complete/without unbalanced entries
                search = re.search(r'BOOKYEAR(\d+).STATUS', id)
                if search and search.group(1) and value.lower() == 'open':
                    param_data['openyears'].append(int(search.group(1)))
                # winbooks has 3 different dates on a line : the move date, the move line date, and the period
                # here we get the different periods as it is what matters for the reports
                search = re.search(r'BOOKYEAR(\d+).PERDATE', id)
                if search and search.group(1):
                    param_data['period_date'][int(search.group(1))] = [datetime.strptime(value[i*8:(i+1)*8], '%d%m%Y').date() for i in range(int(len(value)/8))]
        return param_data

    def post_import(self, account_deprecated_ids):
        account_deprecated_ids.write({'deprecated': True})  # We can't set it before because of a constraint in aml's create

    def import_winbooks_file(self):
        """Import all the data from a Winbooks database dump. The imported
        models are the journals, the accounts, the taxes, the journal entries,
        and the analytic account and lines.
        """
        if not DBF:
            raise UserError(_('dbfread library not found, Winbooks Import features disabled. If you plan to use it, please install the dbfread library from https://pypi.org/project/dbfread/'))
        if not self.env.company.country_id:
            action = self.env.ref('base.action_res_company_form')
            raise RedirectWarning(_('Please define the country on your company.'), action.id, _('Company Settings'))
        if not self.env.company.chart_template_id:
            action = self.env.ref('account.action_account_config')
            raise RedirectWarning(_('You should install a Fiscal Localization first.'), action.id,  _('Accounting Settings'))
        self = self.with_context(active_test=False)
        with tools.osutil.tempdir() as file_dir:
            zip_ref = zipfile.ZipFile(io.BytesIO(base64.decodebytes(self.zip_file)))
            zip_ref.extractall(file_dir)
            child_zip = [s for s in listdir(file_dir) if "@cie@" in s.lower() and '.zip' in s.lower()]
            if child_zip:
                with zipfile.ZipFile(join(file_dir, child_zip[0]), 'r') as child_zip_ref:
                    child_zip_ref.extractall(file_dir)
            onlyfiles = [f for f in listdir(file_dir) if isfile(join(file_dir, f))]
            csffile = [s for s in onlyfiles if "_csf.dbf" in s.lower()]
            acffile = [s for s in onlyfiles if "_acf.dbf" in s.lower()]
            actfile = [s for s in onlyfiles if "_act.dbf" in s.lower()]
            antfile = [s for s in onlyfiles if "_ant.dbf" in s.lower()]
            anffile = [s for s in onlyfiles if "_anf.dbf" in s.lower()]
            tablefile = [s for s in onlyfiles if "_table.dbf" in s.lower()]
            vatfile = [s for s in onlyfiles if "_codevat.dbf" in s.lower()]
            dbkfile = [s for s in onlyfiles if "dbk" in s.lower() and s.lower().endswith('.dbf')]
            scanfile = [s for s in onlyfiles if "@scandbk" in s.lower() and s.lower().endswith('.zip')]
            paramfile = [s for s in onlyfiles if "_param.dbf" in s.lower()]
            param_data = self.import_param(file_dir, paramfile)
            journal_data = self.import_journal(file_dir, dbkfile)
            account_data, account_central, account_deprecated_ids, account_tax = self.import_account(file_dir, acffile, journal_data)
            vatcode_data = self.import_vat(file_dir, vatfile, account_central)
            self.post_process_account(account_data, vatcode_data, account_tax)
            civility_data, category_data = self.import_partner_info(file_dir, tablefile)
            partner_data = self.import_partner(file_dir, csffile, civility_data, category_data, account_data)
            self._import_move(file_dir, actfile, scanfile, account_data, account_central, journal_data, partner_data, vatcode_data, param_data)
            analytic_account_data = self.import_analytic_account(file_dir, anffile)
            self.import_analytic_account_line(file_dir, antfile, analytic_account_data, account_data)
            self.post_import(account_deprecated_ids)
            _logger.info("Completed")
            self.env.company.sudo().set_onboarding_step_done('account_onboarding_winbooks_state')
            self.env.company.sudo().set_onboarding_step_done('account_setup_coa_state')
        return True
