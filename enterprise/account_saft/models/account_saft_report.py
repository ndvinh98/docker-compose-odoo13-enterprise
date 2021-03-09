# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import re
import xml.dom.minidom
from io import BytesIO
from collections import defaultdict

from odoo import fields, models, tools, release, _
from odoo.exceptions import UserError


class AccountGeneralLedger(models.AbstractModel):
    _inherit = "account.general.ledger"

    def _prepare_header_data(self, options):
        company = self.env.company
        return {
            'country': company.country_id.code,
            'date_created': fields.Date.today(),
            'software_version': release.version,
            'company_currency': company.currency_id.name,
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
        }

    def _prepare_company_data(self):
        # RegistrationNumber for company is mandatory for CompanyHeaderStructure element
        company = self.env.company
        if not company.company_registry:
            raise UserError(_('Define `Company Registry` for your company.'))
        partner_id = company.partner_id.id
        child_ids = company.partner_id.child_ids.ids
        company_details = self._get_addresses_and_contacts(child_ids + [partner_id])[partner_id]

        return {
            'id': company.id,
            'name': company.name,
            'company_registry': company.company_registry,
            'addresses': company_details.get('addresses') or [company_details['default_value']],
            'contacts': company_details.get('contacts') or [company_details['default_value']],
            'vat': company.vat,
            'bank_accounts': self._prepare_bank_account_data(company.bank_ids),
        }

    def _prepare_bank_account_data(self, banks):
        bank_account_list = []
        for bank in banks:
            bank_account_list.append({
                'iban': True if bank.acc_type == 'iban' else False,
                'bank_name': bank.bank_name if bank.bank_name else '',
                'acc_number': bank.acc_number,
                'bank_bic': bank.bank_bic,
            })

        return bank_account_list

    def _format_debit_credit(self, amount):
        if amount > 0:
            debit = abs(amount)
            credit = 0.0
        else:
            debit = 0.0
            credit = abs(amount)

        return {
            'debit': '%.2f' % debit,
            'credit': '%.2f' % credit,
        }

    def _prepare_account_master_data(self, options):
        options['unfold_all'] = True
        options_list = self._get_options_periods_list(options)
        accounts_results, taxes_results = self._do_query(options_list)
        account_list = []

        for account, periods_results in accounts_results:
            results = periods_results[0]
            account_init_bal = results.get('initial_balance', {})
            account_un_earn = results.get('unaffected_earnings', {})
            account_balance = results.get('sum', {})
            opening_amount = (account_init_bal.get('debit', 0.0) + account_un_earn.get('debit', 0.0)) - \
                                (account_init_bal.get('credit', 0.0) + account_un_earn.get('credit', 0.0))
            closing_amount = account_balance.get('debit', 0.0) - account_balance.get('credit', 0.0)
            account_list.append({
                'id': account.id,
                'name': account.name,
                'code': account.code,
                'group_code': account.group_id.id or "",
                'group_categ': account.group_id and account.group_id.name or "",
                'account_type': account.user_type_id.name,
                'opening_balance': self._format_debit_credit(opening_amount),
                'closing_balance': self._format_debit_credit(closing_amount)
            })
        return account_list

    def _prepare_partner_master_data(self, options):
        options['unfold_all'] = True
        options['account_type'] = [
            {'id': 'receivable', 'name': 'Receivable', 'selected': False},
            {'id': 'payable', 'name': 'Payable', 'selected': False}
        ]
        partners_results = self.env['account.partner.ledger']._do_query(options)
        customers_list = []
        suppliers_list = []
        Move = self.env['account.move']
        sale_types = Move.get_sale_types()
        purchase_types = Move.get_purchase_types()
        partners = self.env['res.partner']
        for partner, results in partners_results:
            partners |= partner

        all_partner_details = self._get_addresses_and_contacts(partners.mapped('child_ids').ids + partners.ids)

        for partner, results in partners_results:
            partner_sum = results.get('sum', {})
            partner_init_bal = results.get('initial_balance', {})

            opening_amount = partner_init_bal.get('debit', 0) - partner_init_bal.get('credit', 0)
            closing_amount = (partner_init_bal.get('debit', 0) + partner_sum.get('debit', 0)) - \
                                (partner_init_bal.get('credit', 0) + partner_sum.get('credit', 0))

            partner_details = all_partner_details.get(partner.id, {})
            partner_data = partner_details['default_value']
            addresses = partner_details.get('addresses')
            contacts = partner_details.get('contacts')

            partner_data.update({
                'addresses': addresses or [partner_data],
                'contacts': contacts or [partner_data],
                'bank_accounts': self._prepare_bank_account_data(partner.bank_ids),
                'opening_balance': self._format_debit_credit(opening_amount),
                'closing_balance': self._format_debit_credit(closing_amount),
            })
            lines = results.get('lines') or []
            if any(line.get('move_type') in sale_types for line in lines):
                partner_data['is_customer'] = True
                customers_list.append(partner_data)
            if any(line.get('move_type') in purchase_types for line in lines):
                partner_data['is_supplier'] = True
                suppliers_list.append(partner_data)

        return customers_list, suppliers_list

    def _query_get_partners(self, partner_ids):
        query = '''
            SELECT
                partner.id,
                partner.vat,
                partner.zip,
                partner.name,
                partner.type,
                partner.email,
                partner.website,
                partner.parent_id,
                partner_title.name                                    AS title,
                partner.city                                          AS city,
                country.code                                          AS country,
                partner.street                                        AS street,
                partner.street2                                       AS street2,
                COALESCE(partner.phone, partner.mobile)               AS phone
            FROM res_partner partner
                LEFT JOIN res_country country             ON country.id = partner.country_id
                LEFT JOIN res_partner_title partner_title ON partner.title = partner_title.id
            WHERE partner.id in %s
        '''
        return query, [tuple(set(partner_ids))]

    def _get_addresses_and_contacts(self, partner_ids, invoice_partner=False):
        """Build a dictionary mapping a partner to its contacts and addresses."""
        if not partner_ids:
            return {}

        query, params = self._query_get_partners(partner_ids)
        self._cr.execute(query, params)

        all_partner_details = defaultdict(lambda: {'contacts': [], 'addresses': []})
        # We skip contacts when they don't have city/zip/phone and raise an error when the parent partner does not have one
        for partner_dict in self._cr.dictfetchall():
            partner_id = partner_dict['id']
            parent_partner_id = partner_dict['parent_id']
            if not parent_partner_id:
                # If the partner does not have any contacts and/or addresses, the parent partner's details will be used as contact/address
                all_partner_details[partner_id]['default_value'] = partner_dict
            elif partner_dict['type'] == 'contact':
                if partner_dict['phone']:
                    all_partner_details[parent_partner_id]['contacts'].append(partner_dict)
            else:
                if partner_dict['city'] and partner_dict['zip']:
                    all_partner_details[parent_partner_id]['addresses'].append(partner_dict)

        bad_address_list = [partner['default_value']['name'] for partner in all_partner_details.values()
                            if not partner['addresses'] and not (partner['default_value']['city'] and partner['default_value']['zip'])]
        bad_contact_list = [partner['default_value']['name'] for partner in all_partner_details.values()
                            if not partner['contacts'] and not partner['default_value']['phone']]
        if bad_address_list:
            raise UserError(_("Please define City/Zip for address(es) of `%s`.") % (', '.join(filter(None, bad_address_list))))
        if bad_contact_list:
            raise UserError(_('Please define Phone or Mobile for `%s` Contact(s).' % (', '.join(filter(None, bad_contact_list)))))

        return all_partner_details

    def _get_all_tax_data(self):
        all_taxes = self.env['account.tax'].search_read([('company_id', '=', self.env.company.id)], ['name', 'amount_type', 'amount'])
        return {tax_dict['id']: tax_dict for tax_dict in all_taxes}

    def _get_updated_select_clause(self, select_clause):
        return select_clause + ''',
                account_move_line.move_id,
                account_move_line.tax_line_id,
                account_move_line.journal_id,
                account_move_line.balance,
                account_move_line.price_total,
                account_move_line.price_subtotal,
                account_move_line.exclude_from_invoice_tab,
                account_move_line__move_id.date                               AS move_date,
                account_move_line__move_id.create_date                        AS move_create_date,
                journal.type                                                  AS journal_type,
                journal.name                                                  AS journal_name,
                invoice_line_taxes.taxes_count                                AS invoice_line_taxes_count,
                invoice_line_taxes.taxes                                      AS invoice_line_taxes,
                invoice_line_taxes.tax_id                                     AS invoice_line_tax_id,
                account_type.type                                             AS account_type'''

    def _get_updated_from_clause(self, from_clause):
        return from_clause + ''' LEFT JOIN account_account_type account_type ON account_type.id = account.user_type_id
                                 LEFT JOIN invoice_line_taxes ON account_move_line.id = invoice_line_taxes.account_move_line_id'''

    def _get_updated_query_amls(self, options):
        query, where_params = self._get_query_amls(options, False)
        query_select, query_rest = query.split("FROM")
        query_from, where_clause = query_rest.split("WHERE")
        select_clause = self._get_updated_select_clause(query_select)
        from_clause = self._get_updated_from_clause(query_from)
        with_statement = ''' WITH invoice_line_taxes as (
                    SELECT account_move_line_id, MAX(account_tax_id) as tax_id, COUNT(account_tax_id) taxes_count, ARRAY_AGG(account_tax_id) taxes
                    FROM account_move_line_account_tax_rel
                    GROUP BY account_move_line_id
                ) '''
        query = with_statement + select_clause + ' FROM' + from_clause + ' WHERE' + where_clause
        return query, where_params

    def _get_move_lines(self, options):
        query, where_params = self._get_updated_query_amls(options)
        self._cr.execute(query, where_params)
        return self._cr.dictfetchall()

    def _prepare_amount_data(self, amount, move_line):
        amount_data = {
            'amount': '%.2f' % amount,
        }
        line_currency_id = move_line.get('currency_id')
        company = self.env.company
        if move_line and line_currency_id and company.currency_id.id != line_currency_id:
            currency = self.env['res.currency'].browse(line_currency_id)
            exchange_rate = currency._get_rates(company, move_line.get('date'))[line_currency_id]
            amount_data.update({
                'currency_code': currency.name,
                'exchange_rate': '%.8f' % exchange_rate,
            })
            if 'amount_tax' in move_line:
                amount_data['amount_currency'] = '%.2f' % abs(move_line['amount_tax'])
            else:
                amount_data['amount_currency'] = '%.2f' % abs(move_line['amount_currency'])

        return amount_data

    def _convert_amount_to_company_currency(self, amount, currency_id, date):
        line_currency = self.env['res.currency'].browse(currency_id)
        company = self.env.company
        if line_currency != company.currency_id:
            return '%.2f' % line_currency._convert(amount, company.currency_id, company, date)
        else:
            return '%.2f' % amount

    def _prepare_general_ledger_data(self, move_lines_data):
        gl_total_entries = 0
        gl_total_debit = 0
        gl_total_credit = 0

        tax_master_data = {}

        move_data = {}

        move_line_tax_info = {} # dictionary holding tax information for all move lines(to be shown for GeneralLedgerEntries transactions)

        all_tax_data = self._get_all_tax_data()

        for move_line in move_lines_data:
            move_id = move_line['move_id']
            gl_total_credit += move_line['credit']
            gl_total_debit += move_line['debit']

            # When a tax with 0% rate is applied, no move line is created for that, so, we
            # get that tax information from `invoice_line_tax_id`.
            tax_id = move_line.get('tax_line_id') or move_line.get('invoice_line_tax_id')
            if tax_id and not tax_master_data.get(tax_id):
                tax_master_data[tax_id] = all_tax_data[tax_id]

            if move_line.get('credit'):
                move_line['credit_amount'] = self._prepare_amount_data(move_line.get('credit'), move_line)
            else:
                move_line['debit_amount'] = self._prepare_amount_data(move_line.get('debit'), move_line)
            # `move_line` dictionary has most of the data of moves and move lines
            # hence, just updating line_data dictionary to update it
            line_data = {move_line['id']: move_line}

            # build move dictionary with it's lines (to be used for GL entries as well as invoice lines)
            if not move_data.get(move_id):
                move_dict = {
                    'move_id': move_id,
                    'move_date': move_line['move_date'],
                    'move_type': move_line['move_type'],
                    'move_name': move_line['move_name'],
                    'move_create_date': move_line['move_create_date'],
                    'is_customer': move_line['journal_type'] == 'sale',
                    'is_supplier': move_line['journal_type'] == 'purchase',
                    'partner_id': move_line['partner_id'],
                    'journal_data': {
                        'journal_id': move_line['journal_id'],
                        'journal_name': move_line['journal_name'],
                        'journal_type': move_line['journal_type'],
                    },
                    'lines': line_data,
                }
                move_data[move_id] = move_dict
                gl_total_entries += 1 # We need count of only moves
            else:
                move_data[move_id]['lines'].update({move_line['id']: move_line})

            # Tax information needs to be shown along with product lines of the move/transaction, hence,
            # preparing dictionary for the same with product line's ID as it's key.
            if not move_line['exclude_from_invoice_tab'] and move_line['invoice_line_taxes_count']:
                # In case price_total and price_subtotal are not computed (e.g. from the POS), we
                # compute them now from the balance.
                if move_line['price_total'] is None or move_line['price_subtotal'] is None:
                    prices = self.env['account.move.line']._get_price_total_and_subtotal_model(
                        -move_line['balance'],
                        1.0,
                        0.0,
                        self.env['res.currency'].browse(move_line['currency_id']),
                        self.env['product.product'],
                        self.env['res.partner'],
                        self.env['account.tax'].browse(move_line['invoice_line_taxes']),
                        'other',
                    )
                    move_line['price_subtotal'] = prices.get('price_subtotal', 0.0)
                    move_line['price_total'] = prices.get('price_total', 0.0)
                move_line['amount_tax'] = move_line['price_total'] - move_line['price_subtotal']
                tax_amount_signed = self._convert_amount_to_company_currency(move_line['amount_tax'], move_line['currency_id'], move_line['date'])
                tax_line_dict = {
                    'line_id': move_line['id'],
                    'amount_data': self._prepare_amount_data(float(tax_amount_signed), move_line),
                }
                # In cases when there are multiple taxes applied to same invoice line, the taxed amount is grouped
                # and saved in the database. So, tax's name/type/amount_type etc can not be determined.
                if move_line['invoice_line_taxes_count'] == 1:
                    tax_line_dict.update(all_tax_data.get(move_line['invoice_line_tax_id'], {}))
                if not move_line_tax_info.get(move_id):
                    move_line_tax_info[move_id] = [tax_line_dict]
                else:
                    move_line_tax_info[move_id].append(tax_line_dict)

        general_ledger_data = {
            'total_entries': gl_total_entries,
            'total_debit': '%.2f' % gl_total_debit,
            'total_credit': '%.2f' % gl_total_credit,
            'journals': {},
        }

        # group moves by journal and prepare invoices'/bills' list
        for move_id, move_vals in move_data.items():
            journal_data = move_vals.pop('journal_data')
            journal_id = journal_data['journal_id']
            if not general_ledger_data['journals'].get(journal_id):
                general_ledger_data['journals'][journal_id] = journal_data
                general_ledger_data['journals'][journal_id]['moves'] = [move_vals]
            else:
                general_ledger_data['journals'][journal_id]['moves'].append(move_vals)

        return {
            'all_tax_data': all_tax_data,
            'move_data': move_data,
            'taxes': tax_master_data,
            'move_line_tax_info': move_line_tax_info,
            'general_ledger_data': general_ledger_data,
        }

    def _prepare_saft_report_data(self, options):
        company = self.env.company

        header_data = self._prepare_header_data(options)
        company_data = self._prepare_company_data()
        account_master_data = self._prepare_account_master_data(options)

        customer_master_data, supplier_master_data = self._prepare_partner_master_data(options)
        move_lines_data = self._get_move_lines(options)
        data = self._prepare_general_ledger_data(move_lines_data)

        return dict({
            'xmlns': '',
            'country_code': self.env.company.country_id.code,
            'company': self.env.company,
            'header_data': header_data,
            'company_data': company_data, # same will be used to fill <owners> tag
            'accounts': account_master_data,
            'customers': customer_master_data,
            'suppliers': supplier_master_data,
        }, **data)

    # TO BE OVERWRITTEN
    def _get_template(self):
        return 'account_saft.SaftTemplate'

    def _get_xsd_file(self):
        return False

    def get_xml(self, options):
        template = self._get_template()
        if not template:
            return super().get_xml(options)

        # We do not want data from multi companies, just for current selected companies
        'multi_company' in options and options.pop('multi_company')
        report_data = self._prepare_saft_report_data(options)
        rendered_content = self.env['ir.qweb'].render(template, report_data)
        # Indent the XML data and return as Pretty XML string.
        pretty_xml = xml.dom.minidom.parseString(rendered_content).toprettyxml()
        # remove extra new lines
        audit_content = "\n".join(re.split(r'\n\s*\n', pretty_xml))

        xsd_file = self._get_xsd_file()

        # load XSD file which was cached into attachments during SAFT module installation
        attachment = self.env['ir.attachment'].search([('name', '=', 'xsd_cached_{0}'.format(xsd_file.replace('.', '_')))])
        if attachment:
            xsd_datas = base64.b64decode(attachment.datas)
            with BytesIO(xsd_datas) as xsd:
                tools.xml_utils._check_with_xsd(audit_content, xsd)
        return audit_content
