# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from itertools import groupby
from odoo import api, models, fields, _
from odoo.tools.safe_eval import safe_eval
from collections import OrderedDict

class L10nInReportAccount(models.AbstractModel):
    _name = "l10n.in.report.account"
    _description = "GST Report"
    _inherit = "account.report"

    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_partner = True
    filter_journals = True

    def _get_options(self, previous_options=None):
        options = super(L10nInReportAccount, self)._get_options(previous_options)
        options['gst_return_type'] = 'gstr1'
        options['gst_section'] = self.env.context.get('gst_section')
        return options

    def _set_context(self, options):
        ctx = super(L10nInReportAccount, self)._set_context(options)
        if options.get('gst_return_type'):
            ctx['gst_return_type'] = options['gst_return_type']
        if options.get('gst_section'):
            ctx['gst_section'] = options['gst_section']
        return ctx

    def _get_reports_buttons(self):
        return [
            {'name': _('Print Preview'), 'action': 'print_pdf'},
            {'name': _('Export (CSV)'), 'action': 'print_csv'}]

    def print_csv(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'csv',
                'context': self.env.context}
            }

    def print_pdf(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'pdf',
                }
            }

    @api.model
    def _get_report_name(self):
        context = self.env.context
        gst_section = context.get('gst_section', '')
        gst_return_type = context.get('gst_return_type', '')
        report_name = "GSTR-1 Sales Return"
        if gst_section and not context.get('is_report_filename'):
            report_name = self.get_gst_section(gst_return_type, gst_section)
        if gst_section and context.get('is_report_filename'):
            report_name = gst_section
        return report_name

    def get_report_filename(self, options):
        # pass options as context for section related file name
        context = options.copy() or {}
        context.update({'is_report_filename': True})
        return self.with_context(context)._get_report_name().lower().replace(' ', '_')

    def _get_columns_name(self, options):
        columns_name = []
        gst_return_type = options.get('gst_return_type', '')
        gst_section = options.get('gst_section')
        if gst_section:
            model_fields = self.get_gst_section_fields(gst_return_type, gst_section)
            for model_field in model_fields:
                columns_name.append({
                    'name': model_field.get('label', ''),
                    'class': model_field.get('class', '') + ' o_account_reports_level0'})
            return columns_name
        return[{'name': _('Section'), 'class': "o_account_reports_level0"},
               {'name': _('Number of Entries'), 'class': "o_account_reports_level0"},
               {'name': _('Total CGST'), 'class': 'number o_account_reports_level0'},
               {'name': _('Total SGST'), 'class': 'number o_account_reports_level0'},
               {'name': _('Total IGST'), 'class': 'number o_account_reports_level0'},
               {'name': _('Total CESS'), 'class': 'number o_account_reports_level0'}]

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        gst_return_type = options.get('gst_return_type')
        gst_section = options.get('gst_section')
        filter_domain = [
            ('date', '>=', options['date'].get('date_from')),
            ('date', '<=', options['date'].get('date_to'))]
        context = self.env.context
        if context.get('company_ids'):
            filter_domain += [('company_id', 'in', context['company_ids'])]
        if context.get('partner_ids'):
            filter_domain += [
                ('partner_id', 'in', context['partner_ids'].ids)]
        if context.get('partner_categories'):
            filter_domain += [
                ('partner_id.category_id', 'in', context['partner_categories'].ids)]
        filter_domain += self._get_options_journals_domain(options)
        if gst_section:
            model_domain = self.get_gst_section_model_domain(gst_return_type, gst_section)
            fields_values = self.env[model_domain.get('model')].search_read(
                filter_domain + model_domain.get('domain'))
            lines += self.set_gst_section_lines(
                gst_return_type,
                gst_section,
                fields_values)
        else:
            for gst_section, gst_section_name in self.get_gst_section(gst_return_type).items():
                total_cgst = total_sgst = total_igst = total_cess = 0
                move_count_dict = {}
                model_domain = self.get_gst_section_model_domain(gst_return_type, gst_section)
                domain = filter_domain + model_domain.get('domain')
                for read_data in self.env[model_domain.get('model')].search_read(domain, model_domain.get('sum_fields')):
                    total_cess += read_data.get('cess_amount', 0)
                    total_igst += read_data.get('igst_amount', 0)
                    total_cgst += read_data.get('cgst_amount', 0)
                    total_sgst += read_data.get('sgst_amount', 0)
                    move_count_dict.setdefault(read_data.get('account_move_id'))
                columns = [
                    {'value': len(move_count_dict)},
                    {'value': self.format_value(total_cgst), 'class': 'number'},
                    {'value': self.format_value(total_sgst), 'class': 'number'},
                    {'value': self.format_value(total_igst), 'class': 'number'},
                    {'value': self.format_value(total_cess), 'class': 'number'}]
                lines.append({
                    'id': '%s_%s' % (gst_return_type, gst_section),
                    'name': gst_section_name,
                    'level': 2,
                    'colspan': 0,
                    'columns': [{
                        'name': v.get('value'),
                        'class': v.get('class', '')} for v in columns],
                    'action_id': self.env.ref('l10n_in_reports.action_l10n_in_report_account').id,
                    'action': 'view_sub_type'
                    })
        return lines

    def get_html(self, options, line_id=None, additional_context=None):
        return super(L10nInReportAccount, self.with_context(options or {})).get_html(options, line_id, additional_context)

    def set_gst_section_lines(self, gst_return_type, gst_section, fields_values):
        gst_section_lines = []
        def _get_gst_section_line(group_lines, first_section, gst_section_fields):
            for groups_line in groups_lines:
                gst_section_lines.append({
                    'id': groups_line.get(first_section['name']),
                    'name': groups_line.get(first_section['name']),
                    'class': 'top-vertical-align',
                    'level': 2,
                    'colspan': 0,
                    'columns': self.set_columns(gst_section_fields, groups_line),
                    'style':'font-weight: normal;'
                    })
        if gst_return_type == 'gstr1':
            gst_section_fields = self.get_gst_section_fields(gst_return_type, gst_section)
            first_section = gst_section_fields.pop(0)
            if gst_section in ['b2b', 'b2cl', 'cdnr', 'cdnur', 'exp']:
                for fields_value in fields_values:
                    gst_section_lines.append({
                        'id': fields_value.get('id'),
                        'caret_options': 'account.invoice.out',
                        'name': fields_value.get('account_move_id')[1],
                        'class': 'top-vertical-align o_account_reports_level2',
                        'level': 1,
                        'colspan': 0,
                        'columns': self.set_columns(gst_section_fields, fields_value),
                        'style':'font-weight: normal;'
                        })
            if gst_section in ['b2cs']:
                groups_lines = self.group_report_lines(
                    ['place_of_supply', 'tax_rate', 'ecommerce_vat', 'b2cs_is_ecommerce'],
                    fields_values,
                    ['price_total', 'cess_amount'])
                _get_gst_section_line(groups_lines, first_section, gst_section_fields)
            if gst_section in ['at', 'atadj']:
                groups_lines = self.group_report_lines(
                    ['place_of_supply', 'tax_rate'],
                    fields_values,
                    ['gross_amount', 'cess_amount'])
                _get_gst_section_line(groups_lines, first_section, gst_section_fields)
            if gst_section in ['hsn']:
                groups_lines = self.group_report_lines(
                    ['hsn_code', 'hsn_description', 'l10n_in_uom_code'],
                    fields_values,
                    ['total', 'quantity', 'price_total', 'cgst_amount', 'sgst_amount', 'igst_amount', 'cess_amount'])
                _get_gst_section_line(groups_lines, first_section, gst_section_fields)
            if gst_section in ['exemp']:
                groups_lines = self.group_report_lines(
                    ['out_supply_type'],
                    fields_values,
                    ['nil_rated_amount', 'exempted_amount', 'non_gst_supplies'])
                _get_gst_section_line(groups_lines, first_section, gst_section_fields)
        return gst_section_lines

    def set_columns(self, gst_section_fields, fields_value):
        columns = []
        for section_field in gst_section_fields:
            field_value = fields_value.get(section_field.get('name'))
            # Read m2o field's value from search_read's result
            if isinstance(field_value, tuple):
                field_value = field_value[1]
            if isinstance(field_value, bool) and not field_value:
                field_value = ''
            columns.append({
                'name': field_value,
                'class': section_field.get('class', '')
                })
        return columns

    def group_report_lines(self, group_fields, fields_values, fields):
        res = []
        fields_values = sorted(fields_values, key=lambda s: [s.get(g, '') for g in group_fields])
        for key, grouped_values in groupby(fields_values, lambda x: [x.get(g, '') for g in group_fields]):
            vals = {}
            first_grouped_value = {}
            for grouped_value in grouped_values:
                for field in fields:
                    vals.setdefault(str(field), 0)
                    vals[field] += grouped_value.get(field, 0)
                first_grouped_value.update(grouped_value)
            for group_field in group_fields:
                vals.setdefault(group_field, first_grouped_value.get(group_field, ''))
            res.append(vals)
        return res

    def view_sub_type(self, options, params):
        gst_id = params.get('id').split('_')
        gst_return_type = gst_id[0]
        gst_section = gst_id[1] if len(gst_id) > 1 else None
        [action_read] = self.env['ir.actions.client'].browse(int(params.get('actionId'))).read()
        context = action_read.get('context') and safe_eval(action_read['context']) or {}
        context.update({'gst_return_type': gst_return_type, 'gst_section': gst_section})
        action_read['context'] = context
        display_name = gst_return_type.upper()
        if gst_section:
            display_name = self.get_gst_section(gst_return_type, gst_section)
        action_read['display_name'] = display_name
        return action_read

    # pass gst_section if need full name
    def get_gst_section(self, gst_return_type, gst_section=None):
        gst_sections_list = []
        if gst_return_type == 'gstr1':
            gst_sections_list += [
                {'b2b': _("B2B Invoice - 4A, AB, 4C, 6B, 6C")},
                {'b2cl': _("B2C(Large) Invoice - 5A, 5B")},
                {'b2cs': _("B2C(Small) Details - 7")},
                {'cdnr': _("Credit/Debit Notes(Registered) - 9B")},
                {'cdnur': _("Credit/Debit Notes(Unregistered) - 9B")},
                {'exp': _("Exports Invoice - 6A")},
                {'at': _("Tax Liability(Advances Received) - 11(A), 11A(2)")},
                {'atadj': _("Adjustments of Advances - 11B(1), 11B(2)")},
                {'hsn': _("HSN-wise Summary of Outward Supplies - 12")},
                {'exemp': _("Summary For Nil rated, exempted and non GST outward supplies (8)")}
                ]
        gst_section_full_name = OrderedDict({})
        for gst_section_list in gst_sections_list:
            gst_section_full_name.update(OrderedDict(gst_section_list))
        if gst_section:
            return gst_section_full_name.get(gst_section, '')
        return gst_section_full_name

    def get_gst_section_model_domain(self, gst_return_type, gst_section):
        domain = []
        sum_fields = [
            'account_move_id', 'cess_amount',
            'igst_amount', 'cgst_amount',
            'sgst_amount']
        model = 'l10n_in.account.invoice.report'
        if gst_return_type == 'gstr1':
            domain += [('journal_id.type', '=', 'sale')]
            if gst_section == 'b2b':
                domain += [
                    ('partner_vat', '!=', False),
                    ('l10n_in_export_type', 'in', ['regular', 'deemed', 'sale_from_bonded_wh', 'sez_with_igst', 'sez_without_igst']),
                    ('move_type', 'not in', ('out_refund', 'in_refund'))]
            elif gst_section == 'b2cl':
                domain += [
                    ('partner_vat', '=', False),
                    ('total', '>', '250000'),
                    ('supply_type', '=', 'Inter State'),
                    ('journal_id.l10n_in_import_export', '!=', True),
                    ('move_type', 'not in', ('out_refund', 'in_refund'))]
            elif gst_section == 'b2cs':
                domain += [
                    '&', '&', '&', ('partner_vat', '=', False), ('journal_id.l10n_in_import_export', '!=', True), ('move_type', 'not in', ('out_refund', 'in_refund')),
                    '|', ('supply_type', '=', 'Intra State'),
                    '&', ('total', '<=', '250000'), ('supply_type', '=', 'Inter State')]
            elif gst_section == 'cdnr':
                domain += [
                    ('partner_vat', '!=', False),
                    ('move_type', 'in', ['out_refund', 'in_refund'])]
            elif gst_section == 'cdnur':
                domain += [
                    ('partner_vat', '=', False),
                    ('move_type', 'in', ['out_refund', 'in_refund'])]
            elif gst_section == 'exp':
                domain += [
                    ('journal_id.l10n_in_import_export', '=', True),
                    ('move_type', 'not in', ('out_refund', 'in_refund'))]
            elif gst_section == 'at':
                model = 'l10n_in.advances.payment.report'
                domain = [
                    ('amount', '>', 0),
                    ('payment_type', '=', 'inbound')]
            elif gst_section == 'atadj':
                model = 'l10n_in.advances.payment.adjustment.report'
                domain = [
                    ('payment_type', '=', 'inbound')]
            elif gst_section == 'hsn':
                model = 'l10n_in.product.hsn.report'
            elif gst_section == 'exemp':
                sum_fields = ['account_move_id']
                model = 'l10n_in.exempted.report'
                domain += [
                    ('out_supply_type', '!=', False),
                    '|', ('nil_rated_amount', '!=', 0),
                    '|', ('exempted_amount', '!=', 0),
                    ('non_gst_supplies', '!=', 0)]
            return {'model': model, 'domain': domain}
        return {'model': model, 'domain': domain, 'sum_fields': sum_fields}

    def get_gst_section_fields(self, gst_return_type, gst_section):
        section_fields = []
        if gst_return_type == 'gstr1':
            if gst_section == 'b2b':
                section_fields += [
                    {"name": "account_move_id", "label": "Invoice Number"},
                    {"name": "partner_vat", "label": "GSTIN/UIN of Recipient"},
                    {"name": "partner_id", "label": "Receiver Name"},
                    {"name": "gst_format_date", "label": "Invoice date"},
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "is_reverse_charge", "label": "Reverse Charge"},
                    {"name": "b2b_type", "label": "Invoice Type"},
                    {"name": "ecommerce_vat", "label": "E-Commerce GSTIN", 'class': 'print_only'},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "total", "label": "Invoice Value", "class": "number"},
                    {"name": "price_total", "label": "Taxable Value", "class": "number"},
                    {"name": "cess_amount", "label": "Cess Amount", "class": "number"}
                    ]
            elif gst_section == 'b2cl':
                section_fields = [
                    {"name": "account_move_id", "label": "Invoice Number"},
                    {"name": "gst_format_date", "label": "Invoice date"},
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "ecommerce_vat", "label": "E-Commerce GSTIN", 'class': 'print_only'},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "total", "label": "Invoice Value", "class": "number"},
                    {"name": "price_total", "label": "Taxable Value", "class": "number"},
                    {"name": "cess_amount", "label": "Cess Amount", "class": "number"}
                    ]
            elif gst_section == 'b2cs':
                section_fields = [
                    {"name": "b2cs_is_ecommerce", "label": "Type"},
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "price_total", "label": "Taxable Value", "class": "number"},
                    {"name": "cess_amount", "label": "Cess Amount", "class": "number"},
                    {"name": "ecommerce_vat", "label": "E-Commerce GSTIN"}
                    ]
            elif gst_section == 'cdnr':
                section_fields = [
                    {"name": "account_move_id", "label": "Note/Refund Voucher Number"},
                    {"name": "gst_format_date", "label": "Note/Refund Voucher date"},
                    {"name": "partner_vat", "label": "GSTIN/UIN of Recipient"},
                    {"name": "partner_id", "label": "Receiver Name"},
                    {"name": "reversed_entry_id", "label": "Invoice/Advance Receipt Number"},
                    {"name": "gst_format_refund_date", "label": "Invoice/Advance Receipt date", 'class': 'print_only'},
                    {"name": "refund_invoice_type", "label": "Document Type", 'class': 'print_only'},
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "is_pre_gst", "label": "Pre GST", 'class': 'print_only'},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "total", "label": "Note/Refund Voucher Value", "class": "number"},
                    {"name": "price_total", "label": "Taxable Value", "class": "number"},
                    {"name": "cess_amount", "label": "Cess Amount", "class": "number"}
                    ]
            elif gst_section == 'cdnur':
                section_fields = [
                    {"name": "account_move_id", "label": "Note/Refund Voucher Number"},
                    {"name": "gst_format_date", "label": "Note/Refund Voucher date"},
                    {"name": "refund_export_type", "label": "UR Type"},
                    {"name": "refund_invoice_type", "label": "Document Type", 'class': 'print_only'},
                    {"name": "reversed_entry_id", "label": "Invoice/Advance Receipt Number"},
                    {"name": "gst_format_refund_date", "label": "Invoice/Advance Receipt date", 'class': 'print_only'},
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "is_pre_gst", "label": "Pre GST", 'class': 'print_only'},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "total", "label": "Note/Refund Voucher Value"},
                    {"name": "price_total", "label": "Taxable Value"},
                    {"name": "cess_amount", "label": "Cess Amount"}
                    ]
            elif gst_section == 'exp':
                section_fields = [
                    {"name": "account_move_id", "label": "Invoice Number"},
                    {"name": "gst_format_date", "label": "Invoice date"},
                    {"name": "export_type", "label": "Export Type"},
                    {"name": "shipping_port_code_id", "label": "Port Code"},
                    {"name": "shipping_bill_number", "label": "Shipping Bill Number"},
                    {"name": "gst_format_shipping_bill_date", "label": "Shipping Bill Date"},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "total", "label": "Invoice Value"},
                    {"name": "price_total", "label": "Taxable Value"}
                    ]
            elif gst_section == 'at':
                section_fields = [
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "gross_amount", "label": "Gross Advance Received"},
                    {"name": "cess_amount", "label": "Cess Amount"}
                    ]
            elif gst_section == 'atadj':
                section_fields = [
                    {"name": "place_of_supply", "label": "Place Of Supply"},
                    {"name": "tax_rate", "label": "Rate"},
                    {"name": "gross_amount", "label": "Gross Advance Adjusted"},
                    {"name": "cess_amount", "label": "Cess Amount"}
                    ]
            elif gst_section == 'hsn':
                section_fields = [
                    {"name": "hsn_code", "label": "HSN"},
                    {"name": "hsn_description", "label": "Description"},
                    {"name": "l10n_in_uom_code", "label": "UQC"},
                    {"name": "quantity", "label": "Total Quantity"},
                    {"name": "total", "label": "Total Value"},
                    {"name": "price_total", "label": "Taxable Value"},
                    {"name": "igst_amount", "label": "Integrated Tax Amount"},
                    {"name": "cgst_amount", "label": "Central Tax Amount"},
                    {"name": "sgst_amount", "label": "State/UT Tax Amount"},
                    {"name": "cess_amount", "label": "Cess Amount"}
                    ]
            elif gst_section == 'exemp':
                section_fields = [
                    {"name": "out_supply_type", "label": "Description"},
                    {"name": "nil_rated_amount", "label": "Nil Rated Supplies"},
                    {"name": "exempted_amount", "label": "Exempted(other than nil rated/non GST supply)"},
                    {"name": "non_gst_supplies", "label": "Non-GST Supplies"}
                    ]
        return section_fields

    def get_csv(self, options):
        headers = []
        for row in self.get_header(options):
            header = u''
            for columns in row:
                if not header:
                    header += u'%s' % columns.get('name')
                else:
                    header += u',%s' % columns.get('name')
            headers.append(header)
        lines = headers
        for line in self.with_context(self._set_context(options), print_mode=True)._get_lines(options):
            csv_line = u''
            for columns in line.get('columns'):
                if not csv_line:
                    csv_line += u'"%s"' % columns.get('name')
                else:
                    csv_line += u',"%s"' % columns.get('name')
            if csv_line:
                lines.append(u'"%s",' % line.get('name') + csv_line)
            else:
                lines.append(u'"%s"' % line.get('name'))
        return u'\n'.join(lines).encode('utf-8') + b'\n'
