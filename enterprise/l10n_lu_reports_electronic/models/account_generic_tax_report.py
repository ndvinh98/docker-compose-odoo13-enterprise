# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from odoo import fields, models, tools


class AccountGenericTaxReport(models.AbstractModel):
    _inherit = "account.generic.tax.report"

    def _is_lu_electronic_report(self):
        return self.env.company.country_id.code == 'LU'

    def _get_lu_electronic_report_values(self, options):
        lu_template_values = super()._get_lu_electronic_report_values(options)

        lines = self.with_context(self._set_context(options))._get_lines(options)

        values = {}
        for line in lines:
            # tax report's `code` would contain alpha-numeric string like `LUTAX_XXX` where characters
            # at last three positions will be digits, hence we split `code` with `_` and build dictionary
            # having `code` as dictionary key
            split_line_code = line.get('line_code') and line['line_code'].split('_') or []
            if len(split_line_code) > 1 and split_line_code[1].isdigit():
                balance = "{:.2f}".format(line['columns'][0]['balance']).replace('.', ',')
                values[split_line_code[1]] = {'value': balance, 'field_type': 'number'}

        on_payment = self.env['account.tax'].search([
            ('company_id', '=', self.env.company.id), ('tax_exigibility', '=', 'on_payment')], limit=1)
        values['204'] = {'value': on_payment and '0' or '1', 'field_type': 'boolean'}
        values['205'] = {'value': on_payment and '1' or '0', 'field_type': 'boolean'}

        date_from = fields.Date.from_string(options['date'].get('date_from'))
        date_to = fields.Date.from_string(options['date'].get('date_to'))

        # When user selects custom dates, if its start and end date fall in the same month,
        # the report declaration will be considered monthly. If both dates fall in the same quarter,
        # it will be considered quarterly report. If both datas fall in different quarters,
        # it will be considered a yearly report.
        date_from_quarter = tools.date_utils.get_quarter_number(date_from)
        date_to_quarter = tools.date_utils.get_quarter_number(date_to)
        if date_from.month == date_to.month:
            period = date_from.month
            declaration_type = 'TVA_DECM'
        elif date_from_quarter == date_to_quarter:
            period = date_from_quarter
            declaration_type = 'TVA_DECT'
        else:
            period = 1
            declaration_type = 'TVA_DECA'

        lu_template_values.update({
            'forms': [{
                'declaration_type': declaration_type,
                'year': date_from.year,
                'period': period,
                'currency': self.env.company.currency_id.name,
                'field_values': values
            }]
        })
        return lu_template_values

    def get_xml(self, options):
        if not self._is_lu_electronic_report():
            return super().get_xml(options)

        self._lu_validate_ecdf_prefix()

        lu_template_values = self._get_lu_electronic_report_values(options)
        rendered_content = self.env.ref('l10n_lu_reports_electronic.l10n_lu_electronic_report_template').render(lu_template_values)
        content = "\n".join(re.split(r'\n\s*\n', rendered_content.decode("utf-8"))) # Remove empty lines
        self._lu_validate_xml_content(content)

        return "<?xml version='1.0' encoding='UTF-8'?>" + content
