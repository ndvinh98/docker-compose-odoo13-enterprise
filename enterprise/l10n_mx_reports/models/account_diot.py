# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import division

from contextlib import contextmanager
import locale
import re
import json
import logging
from unicodedata import normalize
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, float_compare, translate

_logger = logging.getLogger(__name__)


class MxReportPartnerLedger(models.AbstractModel):
    _name = "l10n_mx.account.diot"
    _inherit = "account.report"
    _description = "DIOT"

    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_all_entries = None

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Type of Third')},
            {'name': _('Type of Operation')},
            {'name': _('VAT')},
            {'name': _('Country')},
            {'name': _('Nationality')},
            {'name': _('Paid 16%'), 'class': 'number'},
            {'name': _('Paid 16% - Non-Creditable'), 'class': 'number'},
            {'name': _('Paid 8 %'), 'class': 'number'},
            {'name': _('Paid 8 % - Non-Creditable'), 'class': 'number'},
            {'name': _('Importation 16%'), 'class': 'number'},
            {'name': _('Paid 0%'), 'class': 'number'},
            {'name': _('Exempt'), 'class': 'number'},
            {'name': _('Withheld'), 'class': 'number'},
        ]

    def _do_query_group_by_account(self, options, line_id):
        select = ',\"account_move_line_account_tax_rel\".account_tax_id, SUM(\"account_move_line\".debit - \"account_move_line\".credit)'  # noqa
        sql = "SELECT \"account_move_line\".partner_id%s FROM %s WHERE %s%s AND \"account_move_line_account_tax_rel\".account_move_line_id = \"account_move_line\".id GROUP BY \"account_move_line\".partner_id, \"account_move_line_account_tax_rel\".account_tax_id"  # noqa
        context = self.env.context
        journal_ids = []
        for company in self.env['res.company'].browse(context[
                'company_ids']).filtered('tax_cash_basis_journal_id'):
            journal_ids.append(company.tax_cash_basis_journal_id.id)
        tax_ids = self.env['account.tax'].with_context(active_test=False).search([
            ('type_tax_use', '=', 'purchase'),
            ('tax_exigibility', '=', 'on_payment')])
        account_tax_ids = tax_ids.mapped('invoice_repartition_line_ids.account_id')
        domain = [
            ('journal_id', 'in', journal_ids),
            ('account_id', 'not in', account_tax_ids.ids),
            ('tax_ids', 'in', tax_ids.ids),
            ('date', '>=', context['date_from']),
            ('move_id.state', '=', 'posted'),
        ]
        tables, where_clause, where_params = self.env[
            'account.move.line']._query_get(domain)
        tables += ',"account_move_line_account_tax_rel"'
        line_clause = line_id and\
            ' AND \"account_move_line\".partner_id = ' + str(line_id) or ''
        query = sql % (select, tables, where_clause, line_clause)
        self.env.cr.execute(query, where_params)
        results = self.env.cr.fetchall()
        result = {}
        for res in results:
            result.setdefault(res[0], {}).setdefault(res[1], res[2])
        return result

    def _group_by_partner_id(self, options, line_id):
        partners = {}
        results = self._do_query_group_by_account(options, line_id)
        mx_country = self.env.ref('base.mx')
        context = self.env.context
        journal_ids = []
        for company in self.env['res.company'].browse(
                context['company_ids']).filtered('tax_cash_basis_journal_id'):
            journal_ids.append(company.tax_cash_basis_journal_id.id)
        tax_ids = self.env['account.tax'].with_context(active_test=False).search([
            ('type_tax_use', '=', 'purchase'),
            ('tax_exigibility', '=', 'on_payment')])
        account_tax_ids = tax_ids.mapped('invoice_repartition_line_ids.account_id')
        base_domain = [
            ('date', '<=', context['date_to']),
            ('company_id', 'in', context['company_ids']),
            ('journal_id', 'in', journal_ids),
            ('account_id', 'not in', account_tax_ids.ids),
            ('tax_ids', 'in', tax_ids.ids),
        ]

        if context['date_from_aml']:
            base_domain.append(('date', '>=', context['date_from_aml']))
        without_vat = []
        without_too = []
        for partner_id, result in results.items():
            domain = list(base_domain)  # copying the base domain
            domain.append(('partner_id', '=', partner_id))
            partner = self.env['res.partner'].browse(partner_id)
            partners[partner] = result
            if not context.get('print_mode'):
                #  fetch the 81 first amls. The report only displays the first
                # 80 amls. We will use the 81st to know if there are more than
                # 80 in which case a link to the list view must be displayed.
                partners[partner]['lines'] = self.env[
                    'account.move.line'].search(domain, order='date', limit=81)
            else:
                partners[partner]['lines'] = self.env[
                    'account.move.line'].search(domain, order='date')

            if partner.country_id == mx_country and not partner.vat and partners[partner]['lines']:
                without_vat.append(partner.name)

            if not partner.l10n_mx_type_of_operation and partners[partner]['lines']:
                without_too.append(partner.name)

        if (without_vat or without_too) and self._context.get('raise'):
            msg = _('The report cannot be generated because of: ')
            msg += (
                _('\n\nThe following partners do not have a '
                  'valid RFC: \n - %s') %
                '\n - '.join(without_vat) if without_vat else '')
            msg += (
                _('\n\nThe following partners do not have a '
                  'type of operation: \n - %s') %
                '\n - '.join(without_too) if without_too else '')
            msg += _(
                '\n\nPlease fill the missing information in the partners and '
                'try again.')

            raise UserError(msg)

        return partners

    @api.model
    def get_taxes_with_financial_tag(self, tag_xmlid, allowed_tax_ids):
         rep_lines = self.env['account.tax.repartition.line'].search([
             '|', ('invoice_tax_id', 'in', allowed_tax_ids), ('refund_tax_id', 'in', allowed_tax_ids),
             ('tag_ids', 'in', self.env['ir.model.data'].xmlid_to_res_id(tag_xmlid))])

         return rep_lines.mapped('invoice_tax_id') | rep_lines.mapped('refund_tax_id')

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        if line_id:
            line_id = line_id.replace('partner_', '')
        context = self.env.context
        grouped_partners = self.with_context(date_from_aml=context[
            'date_from'])._group_by_partner_id(options, line_id)
        # Aml go back to the beginning of the user chosen range but the
        # amount on the partner line should go back to either the beginning of
        # the fy or the beginning of times depending on the partner
        sorted_partners = sorted(grouped_partners, key=lambda p: p.name or '')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines')
        tag_16 = self.env.ref('l10n_mx.tag_diot_16')
        tag_non_cre = self.env.ref('l10n_mx.tag_diot_16_non_cre', raise_if_not_found=False) or self.env['account.account.tag']
        tag_8 = self.env.ref('l10n_mx.tag_diot_8', raise_if_not_found=False) or self.env['account.account.tag']
        tag_8_non_cre = self.env.ref('l10n_mx.tag_diot_8_non_cre', raise_if_not_found=False) or self.env['account.account.tag']
        tag_imp = self.env.ref('l10n_mx.tag_diot_16_imp')
        tag_0 = self.env.ref('l10n_mx.tag_diot_0')
        tag_ret = self.env.ref('l10n_mx.tag_diot_ret')
        tag_exe = self.env.ref('l10n_mx.tag_diot_exento')
        rep_line_obj =  self.env['account.tax.repartition.line'].with_context(active_test=False)

        purchase_tax_ids = self.env['account.tax'].with_context(active_test=False).search([('type_tax_use', '=', 'purchase')]).ids
        diot_common_domain = ['|', ('invoice_tax_id', 'in', purchase_tax_ids), ('refund_tax_id', 'in', purchase_tax_ids)]

        company = self.env.company.id
        tax16 = rep_line_obj.search([('tag_ids', 'in', tag_16.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        taxnoncre = self.env['account.tax']
        if tag_non_cre:
            taxnoncre = rep_line_obj.search([('tag_ids', 'in', tag_non_cre.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        tax8 = self.env['account.tax']
        if tag_8:
            tax8 = rep_line_obj.search([('tag_ids', 'in', tag_8.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        tax8_noncre = self.env['account.tax']
        if tag_8_non_cre:
            tax8_noncre = rep_line_obj.search([('tag_ids', 'in', tag_8_non_cre.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        taximp = rep_line_obj.search([('tag_ids', 'in', tag_imp.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        tax0 = rep_line_obj.search([('tag_ids', 'in', tag_0.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        tax_ret = rep_line_obj.search([('tag_ids', 'in', tag_ret.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        tax_exe = rep_line_obj.search([('tag_ids', 'in', tag_exe.ids), ('company_id', '=', company)] + diot_common_domain).mapped('tax_id')
        grouped_taxes = self.env['account.tax'].with_context(active_test=False).search([
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', company),
            ('amount_type', '=', 'group')])
        taxes_in_groups = self.env['account.tax'].with_context(active_test=False)
        if grouped_taxes:
            self.env.cr.execute(
                """
                SELECT child_tax
                FROM account_tax_filiation_rel
                WHERE parent_tax IN %s
                """, [tuple(grouped_taxes.ids)])
            taxes_in_groups = taxes_in_groups.browse([x[0] for x in self.env.cr.fetchall()])
        for partner in sorted_partners:
            amls = grouped_partners[partner]['lines']
            if not amls:
                continue
            if not partner:
                for line in amls:
                    lines.append({
                        'id': str(line.id),
                        'name': '',
                        'columns': [{'name': ''}],
                        'level': 1,
                        'colspan': 10
                    })
                continue
            p_columns = [
                partner.l10n_mx_type_of_third or '', partner.l10n_mx_type_of_operation or '',
                partner.vat or '', partner.country_id.code or '',
                self.str_format(partner.l10n_mx_nationality, True)]
            partner_data = grouped_partners[partner]
            total_tax16 = total_taximp = total_tax8 = 0
            total_tax0 = total_taxnoncre = total_tax8_noncre = 0
            exempt = 0
            withh = 0
            for tax in tax16:
                if tax in taxes_in_groups:
                    diff = 16 - tax.amount
                    withh += diff * partner_data.get(tax.id, 0) / 100
                total_tax16 += partner_data.get(tax.id, 0)
            p_columns.append(total_tax16)
            for tax in taxnoncre.ids:
                total_taxnoncre += partner_data.get(tax, 0)
            p_columns.append(total_taxnoncre)
            for tax in tax8.ids:
                total_tax8 += partner_data.get(tax, 0)
            p_columns.append(total_tax8)
            for tax in tax8_noncre.ids:
                total_tax8_noncre += partner_data.get(tax, 0)
            p_columns.append(total_tax8_noncre)
            for tax in taximp.ids:
                total_taximp += partner_data.get(tax, 0)
            p_columns.append(total_taximp)
            total_tax0 += sum([partner_data.get(tax, 0) for tax in tax0.ids])
            p_columns.append(total_tax0)
            exempt += sum([partner_data.get(exem, 0)
                           for exem in tax_exe.ids])
            p_columns.append(exempt)
            withh += sum([abs(partner_data.get(ret.id, 0) / (100 / ret.amount))
                          for ret in tax_ret])
            p_columns.append(withh)
            unfolded = 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all
            lines.append({
                'id': 'partner_' + str(partner.id),
                'name': self.str_format(partner.name)[:45],
                'columns': [{'name': v if index < 5 else int(round(v, 0))} for index, v in enumerate(p_columns)],
                'level': 2,
                'unfoldable': True,
                'unfolded': unfolded,
            })
            if not (unfolded):
                continue
            progress = 0
            domain_lines = []
            amls = grouped_partners[partner]['lines']
            too_many = False
            if len(amls) > 80 and not context.get('print_mode'):
                amls = amls[:80]
                too_many = True
            for line in amls:
                line_debit = line.debit
                line_credit = line.credit
                progress = progress + line_debit - line_credit
                name = line.display_name
                name = name[:32] + "..." if len(name) > 35 else name
                columns = ['', '', '', '']
                columns.append('')
                total_tax16 = total_taximp = total_tax8 = 0
                total_tax0 = total_taxnoncre = total_tax8_noncre = 0
                exempt = 0
                withh = 0
                for tax in tax16.filtered(lambda t: t in line.tax_ids):
                    if tax in taxes_in_groups:
                        diff = 16 - tax.amount
                        withh += diff / 100 * (line.debit or line.credit * -1)
                    total_tax16 += line.debit or line.credit * -1
                columns.append(self.format_value(total_tax16))
                total_taxnoncre += sum([
                    line.debit or line.credit * -1
                    for tax in taxnoncre.ids if tax in line.tax_ids.ids])
                columns.append(self.format_value(total_taxnoncre))
                total_tax8 += sum([
                    line.debit or line.credit * -1
                    for tax in tax8.ids if tax in line.tax_ids.ids])
                columns.append(self.format_value(total_tax8))
                total_tax8_noncre += sum([
                    line.debit or line.credit * -1
                    for tax in tax8_noncre.ids if tax in line.tax_ids.ids])
                columns.append(self.format_value(total_tax8_noncre))
                total_taximp += sum([
                    line.debit or line.credit * -1
                    for tax in taximp.ids if tax in line.tax_ids.ids])
                columns.append(self.format_value(total_taximp))
                total_tax0 += sum([
                    line.debit or line.credit * -1
                    for tax in tax0.ids if tax in line.tax_ids.ids])
                columns.append(self.format_value(total_tax0))
                exempt += sum([line.debit or line.credit * -1
                               for exem in tax_exe.ids
                               if exem in line.tax_ids.ids])
                columns.append(self.format_value(exempt))
                withh += sum([
                    abs((line.debit or line.credit * -1) / (100 / ret.amount))
                    for ret in tax_ret
                    if ret.id in line.tax_ids.ids])
                columns.append(self.format_value(withh))
                if line.move_id.is_purchase_document():
                    caret_type = 'account.invoice.in'
                elif line.move_id.is_sale_document():
                    caret_type = 'account.invoice.out'
                elif line.payment_id:
                    caret_type = 'account.payment'
                else:
                    caret_type = 'account.move'
                domain_lines.append({
                    'id': str(line.id),
                    'parent_id': 'partner_' + str(partner.id),
                    'name': name,
                    'columns': [{'name':v} for v in columns],
                    'caret_options': caret_type,
                    'level': 1,
                })
            domain_lines.append({
                'id': 'total_' + str(partner.id),
                'parent_id': 'partner_' + str(partner.id),
                'class': 'o_account_reports_domain_total',
                'name': _('Total') + ' ' + partner.name,
                'columns': [{'name': v if index < 5 else self.format_value(v)} for index, v in enumerate(p_columns)],
                'level': 1,
            })
            if too_many:
                domain_lines.append({
                    'id': 'too_many_' + str(partner.id),
                    'parent_id': 'partner_' + str(partner.id),
                    'name': _('There are more than 80 items in this list, '
                              'click here to see all of them'),
                    'colspan': 10,
                    'columns': [{}],
                    'level': 3,
                })
            lines += domain_lines
        return lines

    __diot_supplier_re = re.compile(u'''[^A-Za-z0-9 Ññ&]''')
    __diot_nationality_re = re.compile(u'''[^rA-Za-z0-9 Ññ]''')

    @staticmethod
    def str_format(text, is_nationality=False):
        if not text:
            return ''
        trans_tab = {
            ord(char): None for char in (
                u'\N{COMBINING GRAVE ACCENT}',
                u'\N{COMBINING ACUTE ACCENT}',
                u'\N{COMBINING DIAERESIS}',
            )
        }
        text_n = normalize(
            'NFKC', normalize('NFKD', text).translate(trans_tab))
        check_re = MxReportPartnerLedger.__diot_supplier_re
        if is_nationality:
            check_re = MxReportPartnerLedger.__diot_nationality_re
        return check_re.sub('', text_n)

    @api.model
    def _get_report_name(self):
        return _('DIOT')

    def _get_reports_buttons(self):
        buttons = super(MxReportPartnerLedger, self)._get_reports_buttons()
        buttons += [{'name': _('Print DIOT (TXT)'), 'sequence': 3, 'action': 'print_txt', 'file_export_type': _('DIOT')}]
        buttons += [{'name': _('Print DPIVA (TXT)'), 'sequence': 4, 'action': 'print_dpiva_txt', 'file_export_type': _('DPIVA')}]
        return buttons

    def print_dpiva_txt(self, options):
        options.update({'is_dpiva': True})
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'txt',
                'financial_id': self.env.context.get('id'),
            }
        }

    def get_txt(self, options):
        ctx = self._set_context(options)
        ctx.update({'no_format':True, 'print_mode':True, 'raise': True})
        if options.get('is_dpiva'):
            return self.with_context(ctx)._l10n_mx_dpiva_txt_export(options)
        return self.with_context(ctx)._l10n_mx_diot_txt_export(options)

    @contextmanager
    def _custom_setlocale(self):
        old_locale = locale.getlocale(locale.LC_TIME)
        try:
            locale.setlocale(locale.LC_TIME, 'es_MX.utf8')
        except locale.Error:
            _logger.info('Error when try to set locale "es_MX". Please '
                         'contact your system administrator.')
        try:
            yield
        finally:
            locale.setlocale(locale.LC_TIME, old_locale)

    def _l10n_mx_dpiva_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ''
        date = fields.datetime.strptime(
            self.env.context['date_from'], DEFAULT_SERVER_DATE_FORMAT)
        with self._custom_setlocale():
            month = date.strftime("%B").capitalize()

        for line in txt_data:
            if not line.get('id').startswith('partner_'):
                continue
            columns = line.get('columns', [])
            if not sum([c.get('name', 0) for c in columns[5:]]):
                continue
            data = [''] * 48
            data[0] = '1.0'  # Version
            data[1] = date.year  # Fiscal Year
            data[2] = 'MES'  # Cabling value
            data[3] = month  # Period
            data[4] = 1  # 1 Because has data
            data[5] = 1  # 1 = Normal, 2 = Complementary (Not supported now).
            data[8] = len([x for x in txt_data if x.get(
                'parent_id') == line.get('id') and 'total' not in x.get(
                    'id', '')])  # Count the operations
            for num in range(9, 26):
                data[num] = '0'
            data[26] = columns[0]['name']
            data[27] = columns[1]['name']
            data[28] = columns[2]['name'] if columns[0]['name'] == '04' else ''
            data[29] = columns[2]['name'] if columns[0]['name'] != '04' else ''
            data[30] = u''.join(line.get('name', '')).encode('utf-8').strip().decode('utf-8') if columns[0]['name'] != '04' else ''
            data[31] = columns[3]['name'] if columns[0]['name'] != '04' else ''
            data[32] = u''.join(columns[4]['name']).encode('utf-8').strip().decode('utf-8') if columns[0]['name'] != '04' else ''
            data[33] = int(columns[5]['name']) if columns[5]['name'] else ''
            data[39] = int(columns[9]['name']) if columns[9]['name'] else ''
            data[44] = int(columns[10]['name']) if columns[10]['name'] else ''
            data[45] = int(columns[11]['name']) if columns[11]['name'] else ''
            data[46] = int(columns[12]['name']) if columns[12]['name'] else ''
            lines += '|%s|\n' % '|'.join(str(d) for d in data)
        return lines

    def _l10n_mx_diot_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ''
        for line in txt_data:
            if not line.get('id').startswith('partner_'):
                continue
            columns = line.get('columns', [])
            if not sum([c.get('name', 0) for c in columns[5:]]):
                continue
            data = [''] * 25
            data[0] = columns[0]['name']
            data[1] = columns[1]['name']
            data[2] = columns[2]['name'] if columns[0]['name'] == '04' else ''
            data[3] = columns[2]['name'] if columns[0]['name'] != '04' else ''
            data[4] = u''.join(line.get('name', '')).encode('utf-8').strip().decode('utf-8') if columns[0]['name'] != '04' else ''
            data[5] = columns[3]['name'] if columns[0]['name'] != '04' else ''
            data[6] = u''.join(columns[4]['name']).encode('utf-8').strip().decode('utf-8') if columns[0]['name'] != '04' else ''
            data[7] = int(columns[5]['name']) if columns[5]['name'] else ''
            data[9] = int(columns[6]['name']) if columns[6]['name'] else ''
            data[12] = int(columns[7]['name']) if columns[7]['name'] else ''
            data[14] = int(columns[8]['name']) if columns[8]['name'] else ''
            data[15] = int(columns[9]['name']) if columns[9]['name'] else ''
            data[20] = int(columns[10]['name']) if columns[10]['name'] else ''
            data[21] = int(columns[11]['name']) if columns[11]['name'] else ''
            data[22] = int(columns[12]['name']) if columns[12]['name'] else ''
            lines += '|'.join(str(d) for d in data) + '\n'
        return lines
