# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _, _lt

_merchandise_export_code = {
    'BE': '29',
    'FR': '21'
}

_merchandise_import_code = {
    'BE': '19',
    'FR': '11'
}

class IntrastatReport(models.AbstractModel):
    _name = 'account.intrastat.report'
    _description = 'Intrastat Report'
    _inherit = 'account.report'

    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_journals = True
    filter_multi_company = None
    filter_with_vat = False
    filter_intrastat_type = [
        {'name': _lt('Arrival'), 'selected': False, 'id': 'arrival'},
        {'name': _lt('Dispatch'), 'selected': False, 'id': 'dispatch'},
    ]
    filter_intrastat_extended = True

    def _get_filter_journals(self):
        #only show sale/purchase journals
        return self.env['account.journal'].search([('company_id', 'in', self.env.companies.ids or [self.env.company.id]), ('type', 'in', ('sale', 'purchase'))], order="company_id, name")

    def _get_columns_name(self, options):
        columns = [
            {'name': ''},
            {'name': _('Date')},
            {'name': _('System')},
            {'name': _('Country Code')},
            {'name': _('Transaction Code')},
            {'name': _('Region Code')},
            {'name': _('Commodity Code')},
            {'name': _('Type')},
        ]
        if options.get('intrastat_extended'):
            columns += [
                {'name': _('Transport Code')},
                {'name': _('Incoterm Code')},
            ]
        columns += [
            {'name': _('Weight')},
            {'name': _('Quantity')},
            {'name': _('Value'), 'class': 'number'},
        ]
        return columns

    @api.model
    def _create_intrastat_report_line(self, options, vals):
        caret_options = 'account.invoice.%s' % (vals['invoice_type'] in ('in_invoice', 'in_refund') and 'in' or 'out')

        columns = [{'name': c} for c in [
            vals['invoice_date'], vals['system'], vals['country_code'], vals['trans_code'],
            vals['region_code'], vals['commodity_code'], vals['type']
        ]]
        if options.get('intrastat_extended'):
            columns += [{'name': c} for c in [
                vals['invoice_transport'] or vals['company_transport'] or '',
                vals['invoice_incoterm'] or vals['company_incoterm'] or '',
            ]]

        columns += [{'name': c} for c in [
            vals['weight'], vals['quantity'], self.format_value(vals['value'])
        ]]

        return {
            'id': vals['id'],
            'caret_options': caret_options,
            'model': 'account.move.line',
            'name': vals['invoice_number'],
            'columns': columns,
            'level': 2,
        }

    @api.model
    def _decode_options(self, options):
        journal_ids = self.env['account.journal'].search([('type', 'in', ('sale', 'purchase'))]).ids
        if options.get('journals'):
            journal_ids = [c['id'] for c in options['journals'] if c.get('selected')] or journal_ids

        if options.get('intrastat_type'):
            incl_arrivals = options['intrastat_type'][0]['selected']
            incl_dispatches = options['intrastat_type'][1]['selected']
            if not incl_arrivals and not incl_dispatches:
                incl_arrivals = incl_dispatches = True
        else:
            incl_arrivals = incl_dispatches = True

        return options['date']['date_from'], options['date']['date_to'], journal_ids, \
            incl_arrivals, incl_dispatches, options.get('intrastat_extended'), options.get('with_vat')

    @api.model
    def _prepare_query(self, date_from, date_to, journal_ids, invoice_types=None, with_vat=False):
        query_blocks, params = self._build_query(date_from, date_to, journal_ids, invoice_types=invoice_types, with_vat=with_vat)
        query = 'SELECT %(select)s FROM %(from)s WHERE %(where)s ORDER BY %(order)s' % query_blocks
        return query, params

    @api.model
    def _build_query(self, date_from, date_to, journal_ids, invoice_types=None, with_vat=False):
        # triangular use cases are handled by letting the intrastat_country_id editable on
        # invoices. Modifying or emptying it allow to alter the intrastat declaration
        # accordingly to specs (https://www.nbb.be/doc/dq/f_pdf_ex/intra2017fr.pdf (§ 4.x))
        select = '''
                row_number() over () AS sequence,
                CASE WHEN inv.type IN ('in_invoice', 'out_refund') THEN %(import_merchandise_code)s ELSE %(export_merchandise_code)s END AS system,
                country.code AS country_code,
                company_country.code AS comp_country_code,
                CASE WHEN inv_line.intrastat_transaction_id IS NULL THEN '1' ELSE transaction.code END AS transaction_code,
                company_region.code AS region_code,
                code.code AS commodity_code,
                inv_line.id AS id,
                prodt.id AS template_id,
                inv.id AS invoice_id,
                inv.currency_id AS invoice_currency_id,
                inv.name AS invoice_number,
                coalesce(inv.date, inv.invoice_date) AS invoice_date,
                inv.type AS invoice_type,
                inv_incoterm.code AS invoice_incoterm,
                comp_incoterm.code AS company_incoterm,
                inv_transport.code AS invoice_transport,
                comp_transport.code AS company_transport,
                CASE WHEN inv_line.intrastat_transaction_id IS NULL THEN '1' ELSE transaction.code END AS trans_code,
                CASE WHEN inv.type IN ('in_invoice', 'out_refund') THEN 'Arrival' ELSE 'Dispatch' END AS type,
                prod.weight * inv_line.quantity * (
                    CASE WHEN inv_line_uom.category_id IS NULL OR inv_line_uom.category_id = prod_uom.category_id
                    THEN 1 ELSE inv_line_uom.factor END
                ) AS weight,
                inv_line.quantity * (
                    CASE WHEN inv_line_uom.category_id IS NULL OR inv_line_uom.category_id = prod_uom.category_id
                    THEN 1 ELSE inv_line_uom.factor END
                ) AS quantity,
                inv_line.price_subtotal AS value
                '''
        from_ = '''
                account_move_line inv_line
                LEFT JOIN account_move inv ON inv_line.move_id = inv.id
                LEFT JOIN account_intrastat_code transaction ON inv_line.intrastat_transaction_id = transaction.id
                LEFT JOIN res_company company ON inv.company_id = company.id
                LEFT JOIN account_intrastat_code company_region ON company.intrastat_region_id = company_region.id
                LEFT JOIN res_partner partner ON inv_line.partner_id = partner.id
                LEFT JOIN res_partner comp_partner ON company.partner_id = comp_partner.id
                LEFT JOIN res_country country ON inv.intrastat_country_id = country.id
                LEFT JOIN res_country company_country ON comp_partner.country_id = company_country.id
                INNER JOIN product_product prod ON inv_line.product_id = prod.id
                LEFT JOIN product_template prodt ON prod.product_tmpl_id = prodt.id
                LEFT JOIN account_intrastat_code code ON prodt.intrastat_id = code.id
                LEFT JOIN uom_uom inv_line_uom ON inv_line.product_uom_id = inv_line_uom.id
                LEFT JOIN uom_uom prod_uom ON prodt.uom_id = prod_uom.id
                LEFT JOIN account_incoterms inv_incoterm ON inv.invoice_incoterm_id = inv_incoterm.id
                LEFT JOIN account_incoterms comp_incoterm ON company.incoterm_id = comp_incoterm.id
                LEFT JOIN account_intrastat_code inv_transport ON inv.intrastat_transport_mode_id = inv_transport.id
                LEFT JOIN account_intrastat_code comp_transport ON company.intrastat_transport_mode_id = comp_transport.id
                '''
        where = '''
                inv.state = 'posted'
                AND inv_line.display_type IS NULL
                AND inv.company_id = %(company_id)s
                AND company_country.id != country.id
                AND country.intrastat = TRUE
                AND coalesce(inv.date, inv.invoice_date) >= %(date_from)s
                AND coalesce(inv.date, inv.invoice_date) <= %(date_to)s
                AND prodt.type != 'service'
                AND inv.journal_id IN %(journal_ids)s
                AND inv.type IN %(invoice_types)s
                AND NOT inv_line.exclude_from_invoice_tab
                '''
        order = 'inv.invoice_date DESC'
        params = {
            'company_id': self.env.company.id,
            'import_merchandise_code': _merchandise_import_code.get(self.env.company.country_id.code, '29'),
            'export_merchandise_code': _merchandise_export_code.get(self.env.company.country_id.code, '19'),
            'date_from': date_from,
            'date_to': date_to,
            'journal_ids': tuple(journal_ids),
        }
        if with_vat:
            where += ' AND partner.vat IS NOT NULL '
        if invoice_types:
            params['invoice_types'] = tuple(invoice_types)
        else:
            params['invoice_types'] = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
        query = {
            'select': select,
            'from': from_,
            'where': where,
            'order': order,
        }
        return query, params

    @api.model
    def _fill_missing_values(self, vals, cache=None):
        ''' Some values are too complex to be retrieved in the SQL query.
        Then, this method is used to compute the missing values fetched from the database.

        :param vals:    A dictionary created by the dictfetchall method.
        :param cache:   A cache dictionary used to avoid performance loss.
        '''
        if cache is None:
            cache = {}

        # Prefetch data before looping
        self.env['product.template'].browse([v['template_id'] for v in vals]).read(['intrastat_id', 'categ_id'])
        self.env['product.category'].search([]).read(['intrastat_id', 'parent_id'])

        for index in range(len(vals)):
            # Check account.intrastat.code
            # If missing, retrieve the commodity code by looking in the product category recursively.
            if not vals[index]['commodity_code']:
                cache_key = 'commodity_code_%d' % vals[index]['template_id']
                if cache_key not in cache:
                    product = self.env['product.template'].browse(vals[index]['template_id'])
                    intrastat_code = product.search_intrastat_code()
                    cache[cache_key] = vals[index]['commodity_code'] = intrastat_code.name
                vals[index]['commodity_code'] = cache.get(cache_key)

            # Check the currency.
            cache_key = 'currency_%d' % vals[index]['invoice_currency_id']
            if cache_key not in cache:
                cache[cache_key] = self.env['res.currency'].browse(vals[index]['invoice_currency_id'])

            company_currency_id = self.env.company.currency_id
            if cache[cache_key] != company_currency_id:
                vals[index]['value'] = cache[cache_key]._convert(vals[index]['value'], company_currency_id, self.env.company, vals[index]['invoice_date'])
        return vals

    @api.model
    def _get_lines(self, options, line_id=None):
        self.env['account.move.line'].check_access_rights('read')

        date_from, date_to, journal_ids, incl_arrivals, incl_dispatches, extended, with_vat = self._decode_options(options)

        invoice_types = []
        if incl_arrivals:
            invoice_types += ['in_invoice', 'out_refund']
        if incl_dispatches:
            invoice_types += ['out_invoice', 'in_refund']

        query, params = self._prepare_query(date_from, date_to, journal_ids, invoice_types=invoice_types, with_vat=with_vat)

        self._cr.execute(query, params)
        query_res = self._cr.dictfetchall()

        # Create lines
        lines = []
        total_value = 0
        for vals in self._fill_missing_values(query_res):
            line = self._create_intrastat_report_line(options, vals)
            lines.append(line)
            total_value += vals['value']

        # Create total line if only one type selected.
        if incl_arrivals != incl_dispatches:
            colspan = 12 if extended else 10
            lines.append({
                'id': 0,
                'name': _('Total'),
                'class': 'total',
                'level': 2,
                'columns': [{'name': v} for v in [self.format_value(total_value)]],
                'colspan': colspan,
            })
        return lines

    @api.model
    def _get_report_name(self):
        return _('Intrastat Report')
