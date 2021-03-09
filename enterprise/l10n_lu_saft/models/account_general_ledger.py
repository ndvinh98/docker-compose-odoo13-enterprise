# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from odoo import models, _
from odoo.exceptions import UserError


class AccountGeneralLedger(models.AbstractModel):
    _inherit = 'account.general.ledger'

    def _get_reports_buttons(self):
        buttons = super()._get_reports_buttons()
        if self.env.company.country_id.code == 'LU':
            buttons.append({'name': _('Export SAF-T (Luxembourg)'), 'sequence': 5, 'action': 'print_xml', 'file_export_type': _('XML')})
        return buttons

    def _prepare_header_data(self, options):
        res = super()._prepare_header_data(options)
        if self.env.company.country_id.code == 'LU':
            res.update({
                'file_version': '2.01',
                'accounting_basis': 'Invoice Accounting',
            })
        return res

    def _get_updated_select_clause(self, select_clause):
        select_clause = super()._get_updated_select_clause(select_clause)
        if self.env.company.country_id.code == 'LU':
            select_clause += ''',
                account_move_line.product_id,
                account_move_line.quantity,
                account_move_line.price_unit,
                account_move_line.product_uom_id,
                account_move_line__move_id.invoice_origin,
                account_move_line__move_id.invoice_date,
                account_move_line__move_id.amount_total_signed,
                account_move_line__move_id.amount_untaxed_signed,
                product.default_code                                          AS product_code,
                uom.name                                                      AS uom,
                CASE
                     WHEN account_move_line__move_id.type = 'out_invoice'
                     THEN 'C'
                     WHEN account_move_line__move_id.type = 'out_refund'
                     THEN 'D'
                     ELSE NULL
                END                                                           AS invoice_line_indicator
            '''
        return select_clause

    def _get_updated_from_clause(self, from_clause):
        from_clause = super()._get_updated_from_clause(from_clause)
        if self.env.company.country_id.code == 'LU':
            from_clause += '''
                LEFT JOIN uom_uom uom                             ON uom.id = account_move_line.product_uom_id
                LEFT JOIN product_product product                 ON product.id =account_move_line.product_id
            '''
        return from_clause

    def _get_query_products(self, product_ids):
        query = '''
            SELECT
                product.id,
                product.barcode,
                product_template.name,
                product.product_tmpl_id,
                product.default_code,
                product_category.name               AS product_category,
                uom.name                            AS standard_uom,
                uom.uom_type                        AS uom_type,
                TRUNC(uom.factor, 8)                AS uom_ratio,
                CASE
                    WHEN uom.factor != 0
                    THEN TRUNC((1.0 / uom.factor), 8)
                    ELSE 0
                END                                 AS ratio,
                base_uom.name                       AS base_uom
            FROM product_product product
                LEFT JOIN product_template          ON product_template.id = product.product_tmpl_id
                LEFT JOIN product_category          ON product_category.id = product_template.categ_id
                LEFT JOIN uom_uom uom               ON uom.id = product_template.uom_id
                LEFT JOIN uom_uom base_uom          ON base_uom.category_id = uom.category_id AND base_uom.uom_type='reference'
            WHERE product.id in %s
            ORDER BY default_code
        '''
        return query, [tuple(set(product_ids))]

    def _prepare_product_master_data(self, product_ids):
        if not product_ids:
            return []
        query, params = self._get_query_products(product_ids)
        self._cr.execute(query, params)
        product_data = self._cr.dictfetchall()

        duplicate_product_codes = []
        empty_product_codes = []
        for product_code, grouped_products in groupby(product_data, key=lambda product: product['default_code']):
            product_list = list(grouped_products)
            if not product_code:
                empty_product_codes.append(product_list[0]['name'])
            elif len(product_list) > 1:
                duplicate_product_codes += [product['name'] for product in product_list]
        if duplicate_product_codes:
            raise UserError(_("Below products has duplicated `Internal Reference`, please make them unique:\n`%s`.") % (', '.join(set(duplicate_product_codes))))
        if empty_product_codes:
            raise UserError(_("Please define `Internal Reference` for below products:\n`%s`.") % (', '.join(set(empty_product_codes))))
        return product_data

    def _prepare_general_ledger_data(self, move_lines_data):
        res = super()._prepare_general_ledger_data(move_lines_data)

        def update_tax_information_totals_dict(tax_information_totals, move_id, tax_line_dict, taxed_amount):
            tax_line_dict.update({
                'amount_data': taxed_amount,
            })
            if not tax_information_totals.get(move_id):
                tax_information_totals[move_id] = [tax_line_dict]
            else:
                tax_information_totals[move_id].append(tax_line_dict)
            return

        if self.env.company.country_id.code == 'LU':
            move_data = res['move_data']
            all_tax_data = res['all_tax_data']

            uom_ids = set()
            product_ids = set()
            partner_ids = set()

            invoice_total_debit = 0
            invoice_total_credit = 0
            invoice_data = {'invoices': []}
            tax_information_totals = {}

            for move_id, move in move_data.items():
                if move['move_type'] in self.env['account.move'].get_sale_types():
                    partner_id = move.get('partner_id')
                    if partner_id:
                        partner_ids.add(partner_id)
                    for line_id, move_line in move['lines'].items():
                        if move_line.get('product_uom_id'):
                            uom_ids.add(move_line['product_uom_id'])
                        if move_line.get('product_id'):
                            product_ids.add(move_line['product_id'])

                        move.update({
                            'invoice_date': move_line['invoice_date'],
                            'amount_total_signed': '%.2f' % move_line['amount_total_signed'],
                            'amount_untaxed_signed': '%.2f' % move_line['amount_untaxed_signed']
                        })

                        # product's unit price and taxed amount is only stored in invoice's currency,
                        # hence, we convert these amounts into company's currency using this function
                        move_line['price_unit_signed'] = self._convert_amount_to_company_currency(move_line['price_unit'], move_line['currency_id'], move_line['date'])

                        # summarised tax payable totals per tax needs to be shown for each transaction,
                        # hence, preparing dictionary for the same.
                        tax_id = move_line.get('tax_line_id') or move_line.get('invoice_line_tax_id')
                        if tax_id:
                            tax_line_dict = all_tax_data.get(tax_id, {}).copy()
                            if move_line.get('tax_line_id'):
                                if move_line.get('credit'):
                                    taxed_amount = self._prepare_amount_data(move_line.get('credit'), move_line)
                                else:
                                    taxed_amount = self._prepare_amount_data(move_line.get('debit'), move_line)
                                update_tax_information_totals_dict(tax_information_totals, move_id, tax_line_dict, taxed_amount)
                            elif tax_line_dict.get('amount') == 0:
                                # this ensures 0 rated taxes shown in document totals
                                update_tax_information_totals_dict(tax_information_totals, move_id, tax_line_dict, self._prepare_amount_data(0, move_line))

                    amount_untaxed_signed = float(move['amount_untaxed_signed'])
                    if move['move_type'] == 'out_invoice':
                        invoice_total_credit += amount_untaxed_signed
                    elif move['move_type'] == 'out_refund':
                        invoice_total_debit += amount_untaxed_signed

                    invoice_data['invoices'].append(move)
                    invoice_data['invoice_total_debit'] = '%.2f' % abs(invoice_total_debit)
                    invoice_data['invoice_total_credit'] = '%.2f' % abs(invoice_total_credit)

            UoM = self.env['uom.uom']
            uoms = UoM.browse(uom_ids)
            non_ref_uoms = uoms.filtered(lambda uom: uom.uom_type != 'reference')
            if non_ref_uoms:
                # search base UoM for UoM master table
                uoms |= UoM.search([('category_id', 'in', non_ref_uoms.mapped('category_id').ids), ('uom_type', '=', 'reference')])

            res.update({
                'uom_data': uoms.read(['name', 'uom_type']),
                'product_data': self._prepare_product_master_data(product_ids),
                'all_partner_details': self._get_addresses_and_contacts(partner_ids, invoice_partner=True),
                'invoice_data': invoice_data,
                'tax_information_totals': tax_information_totals
            })

        return res

    def _prepare_saft_report_data(self, options):
        res = super()._prepare_saft_report_data(options)
        if res['country_code'] == 'LU':
            res['xmlns'] = 'urn:OECD:StandardAuditFile-Taxation/2.00'
        return res

    def _get_xsd_file(self):
        if self.env.company.country_id.code == 'LU':
            return 'FAIA_v_2_01_reduced_version_A.xsd'
        return super()._get_xsd_file()
