# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from lxml import etree
import time
from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from odoo.tools.xml_utils import create_xml_node
from odoo.exceptions import UserError
class ReportL10nLuPartnerVatIntra(models.AbstractModel):
    _name = "l10n.lu.report.partner.vat.intra"
    _description = "Partner VAT Intra"
    _inherit = 'account.report'

    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_journals = True
    filter_multi_company = None

    filter_intrastat_code = None

    @api.model
    def _init_filter_intrastat_code(self, options, previous_options=None):
        if previous_options and 'intrastat_code' in previous_options:
            options['intrastat_code'] = previous_options['intrastat_code']
        else:
            options['intrastat_code'] = [
                {'name': 'L', 'selected': False, 'id': '0-IC-S-G'},
                {'name': 'T', 'selected': False, 'id': '0-ICT-S-G'},
                {'name': 'S', 'selected': False, 'id': '0-IC-S-S'},
            ]

    def _get_columns_name(self, options):
        return [
            {'name': ''},
            {'name': _('Country Code')},
            {'name': _('VAT Number')},
            {'name': _('Code')},
            {'name': _('Amount'), 'class': 'number'},
        ]

    def _get_lines(self, options, line_id=None, get_xml_data=False):
        lines = []
        l_lines = []
        t_lines = []
        s_lines = []
        context = self.env.context
        l_sum = t_sum = s_sum = 0

        query = """
        SELECT partner.vat AS vat,
               SUM(-aml.balance) AS amount,
               tax.name AS tax_name,
               partner.name AS partner_name,
               aml.partner_id
          FROM account_move_line aml
          JOIN res_partner partner ON aml.partner_id = partner.id
          JOIN account_move_line_account_tax_rel aml_tax ON aml_tax.account_move_line_id = aml.id
          JOIN account_tax tax ON aml_tax.account_tax_id = tax.id
          JOIN res_country country ON partner.country_id = country.id
         WHERE tax.name IN %s
           AND aml.parent_state = 'posted'
           AND aml.company_id = %s
           AND aml.date >= %s
           AND aml.date <= %s
         GROUP BY aml.partner_id, partner.name, partner.vat, tax.name, country.code
         ORDER BY tax.name='0-IC-S-S', tax.name='0-ICT-S-G', tax.name='0-IC-S-G', partner_name
        """
        codes = [x['id'] for x in options['intrastat_code'] if x['selected']]
        codes = codes or [x['id'] for x in options['intrastat_code']]
        params = (tuple(codes), self.env.company.id, context.get('date_from'), context.get('date_to'))
        self.env.cr.execute(query, params)

        for row in self.env.cr.dictfetchall():
            if not row['vat']:
                row['vat'] = ''

            amt = row['amount'] or 0.0
            if amt:
                if get_xml_data and not row['vat']:
                    raise UserError(_('Partner "%s" has no VAT Number.') % row['partner_name'])
                country_code = row['vat'][:2].upper()
                intrastat_code = row['tax_name'] == '0-IC-S-G' and 'L' or row['tax_name'] == '0-ICT-S-G' and 'T' or 'S'
                columns = [
                    country_code,
                    row['vat'][2:].replace(' ', '').upper(),
                    intrastat_code,
                    context.get('get_xml_data') and ('%.2f' % amt).replace('.', ',') or amt,
                ]
                if not context.get('no_format', False):
                    currency_id = self.env.company.currency_id
                    columns[3] = formatLang(self.env, columns[3], currency_obj=currency_id)

                if context.get('get_xml_data'):
                    if intrastat_code == 'L':
                        l_sum += amt
                        l_lines.append(columns)
                    elif intrastat_code == 'T':
                        t_sum += amt
                        t_lines.append(columns)
                    else:
                        s_sum += amt
                        s_lines.append(columns)
                else:
                    lines.append({
                        'id': row['partner_id'] if not get_xml_data else False,
                        'caret_options': 'res.partner',
                        'model': 'res.partner',
                        'name': row['partner_name'] if not get_xml_data else False,
                        'columns': [{'name': v } for v in columns],
                        'unfoldable': False,
                        'unfolded': False,
                    })

        if context.get('get_xml_data'):
            return {
                'l_lines': l_lines,
                't_lines': t_lines,
                's_lines': s_lines,
                'l_sum': ('%.2f' % l_sum).replace('.', ','),
                't_sum': ('%.2f' % t_sum).replace('.', ','),
                's_sum': ('%.2f' % s_sum).replace('.', ','),
            }
        return lines

    def _is_lu_electronic_report(self):
        return True

    def get_xml(self, options):
        # Check
        company = self.env.company
        errors = []
        ecdf_prefix = self._lu_validate_ecdf_prefix()
        company_vat = company.partner_id.vat
        if not company_vat:
            errors.append(_('VAT'))
        matr_number = company.matr_number
        if not matr_number:
            errors.append(_('Matr Number'))
        if errors:
            raise UserError(_('The following must be set on your company:\n- %s') % ('\n- '.join(errors)))

        rcs_number = company.company_registry or 'NE'

        file_ref = options['filename']
        company_vat = company_vat.replace(' ', '').upper()[2:]

        date_from = options['date'].get('date_from')
        date_to = options['date'].get('date_to')

        str_date_from = date_from[5:10]
        str_date_to = date_to[5:10]

        dt_from = datetime.strptime(date_from, '%Y-%m-%d')
        dt_to = datetime.strptime(date_to, '%Y-%m-%d')

        month = None
        quarter = None

        # dt_from is 1st day of months 1,4,7 or 10 and dt_to is last day of dt_from month+2
        if dt_from.day == 1 and dt_from.month % 3 == 1 and dt_to == dt_from + relativedelta(day=31, month=dt_from.month + 2):
            quarter = (dt_from.month + 2) / 3
        # dt_from is 1st day & dt_to is last day of same month
        elif dt_from.day == 1 and dt_from + relativedelta(day=31) == dt_to:
            month = date_from[5:7]
        else:
            raise UserError(_('Check from/to dates. XML must cover 1 full month or 1 full quarter.'))

        ctx = self._set_context(options)
        ctx.update({'no_format': True, 'date_from': date_from, 'date_to': date_to, 'get_xml_data': True})
        xml_data = self.with_context(ctx)._get_lines(options, get_xml_data=True)

        xml_data.update({
            "file_ref": file_ref,
            "matr_number": matr_number,
            "rcs_number": rcs_number,
            "company_vat": company_vat,
            "year": date_from[:4],
            "period": month or quarter,
            "type_labes": month and ['TVA_LICM', 'TVA_PSIM'] or ['TVA_LICT', 'TVA_PSIT'],
        })

        rendered_content = self.env['ir.qweb'].render('l10n_lu_reports_electronic.IntrastatLuXMLReport', xml_data)
        return b"<?xml version='1.0' encoding='utf-8'?>" + rendered_content
