# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime, timedelta


class IntrastatReport(models.AbstractModel):
    _inherit = 'account.intrastat.report'

    def _get_reports_buttons(self):
        res = super(IntrastatReport, self)._get_reports_buttons()
        if self.env.company.country_id == self.env.ref('base.be'):
            res += [{'name': _('Export (XML)'), 'sequence': 3, 'action': 'print_xml', 'file_export_type': _('XML')}]
        return res

    @api.model
    def get_xml(self, options):
        ''' Create the xml export.

        :param options: The report options.
        :return: The xml export file content.
        '''
        date_from, date_to, journal_ids, incl_arrivals, incl_dispatches, extended, with_vat = self._decode_options(options)
        date_1 = datetime.strptime(date_from, DEFAULT_SERVER_DATE_FORMAT)
        date_2 = datetime.strptime(date_to, DEFAULT_SERVER_DATE_FORMAT)
        a_day = timedelta(days=1)
        if date_1.day != 1 or (date_2 - date_1) > timedelta(days=30) or date_1.month == (date_2 + a_day).month:
            raise UserError(_('Wrong date range selected. The intrastat declaration export has to be done monthly.'))
        date = date_1.strftime('%Y-%m')

        company = self.env.company
        if not company.company_registry:
            raise UserError(_('Missing company registry information on the company'))

        cache = {}

        # create in_vals corresponding to invoices with cash-in
        in_vals = []
        if incl_arrivals:
            query, params = self._prepare_query(
                date_from, date_to, journal_ids=journal_ids, invoice_types=('in_invoice', 'out_refund'), with_vat=with_vat)
            self._cr.execute(query, params)
            query_res = self._cr.dictfetchall()
            in_vals = self._fill_missing_values(query_res, cache)

        # create out_vals corresponding to invoices with cash-out
        out_vals = []
        if incl_dispatches:
            query, params = self._prepare_query(
                date_from, date_to, journal_ids=journal_ids, invoice_types=('out_invoice', 'in_refund'))
            self._cr.execute(query, params)
            query_res = self._cr.dictfetchall()
            out_vals = self._fill_missing_values(query_res, cache)

        return self.env.ref('l10n_be_intrastat.intrastat_report_export_xml').render({
            'company': company,
            'in_vals': in_vals,
            'out_vals': out_vals,
            'extended': extended,
            'date': date,
            '_get_reception_code': self._get_reception_code,
            '_get_reception_form': self._get_reception_form,
            '_get_expedition_code': self._get_expedition_code,
            '_get_expedition_form': self._get_expedition_form,
        })

    @api.model
    def _build_query(self, date_from, date_to, journal_ids, invoice_types=None, with_vat=False):
        query, params = super(IntrastatReport, self)._build_query(date_from, date_to, journal_ids, invoice_types=invoice_types, with_vat=with_vat)
        # If you don't know the country of origin of the goods, as an exception you may replace the country code by "QU".
        query['select'] += ', CASE WHEN inv_line.intrastat_product_origin_country_id IS NULL THEN \'QU\' ELSE product_country.code END AS intrastat_product_origin_country'
        query['from'] += ' LEFT JOIN res_country product_country ON product_country.id = inv_line.intrastat_product_origin_country_id'
        # For VAT numbers of companies outside the European Union, for example in the case of triangular trade, you always have to use the code "QV999999999999".
        query['select'] += ', CASE WHEN partner_country.id IS NULL THEN \'QV999999999999\' ELSE partner.vat END AS partner_vat'
        query['from'] += ' LEFT JOIN res_country partner_country ON partner.country_id = partner_country.id AND partner_country.intrastat IS TRUE'
        return query, params

    @api.model
    def _get_columns_name(self, options):
        columns = super(IntrastatReport, self)._get_columns_name(options)
        columns += [
            {'name': _('Origin Country')},
            {'name': _('Partner VAT')},
        ]
        return columns

    @api.model
    def _create_intrastat_report_line(self, options, vals):
        res = super(IntrastatReport, self)._create_intrastat_report_line(options, vals)
        res['columns'] += [
            {'name': vals['intrastat_product_origin_country']},
            {'name': vals['partner_vat']},
        ]
        return res

    def _get_reception_code(self, extended):
        return 'EX19E' if extended else 'EX19S'

    def _get_reception_form(self, extended):
        return 'EXF19E' if extended else 'EXF19S'

    def _get_expedition_code(self, extended):
        return 'INTRASTAT_X_E' if extended else 'INTRASTAT_X_S'

    def _get_expedition_form(self, extended):
        return 'INTRASTAT_X_EF' if extended else 'INTRASTAT_X_SF'
