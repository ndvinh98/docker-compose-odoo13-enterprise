# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from odoo import fields, models, tools


class ReportAccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"

    def _get_lu_reports(self):
        return {
            self.env.ref("l10n_lu_reports.account_financial_report_l10n_lu_bs").id : 'CA_BILAN',
            self.env.ref("l10n_lu_reports.account_financial_report_l10n_lu_bs_abr").id : 'CA_BILANABR',
            self.env.ref("l10n_lu_reports.account_financial_report_l10n_lu_pl").id : 'CA_COMPP',
            self.env.ref("l10n_lu_reports.account_financial_report_l10n_lu_pl_abr").id : 'CA_COMPPABR'
        }

    def _is_lu_electronic_report(self):
        return self.id in self._get_lu_reports().keys()

    def _get_lu_electronic_report_values(self, options):

        def _format_amount(amount):
            return "{:.2f}".format(amount).replace('.', ',')

        lu_template_values = super()._get_lu_electronic_report_values(options)

        # Add comparison filter to get data from last year
        self.filter_comparison = {'filter': 'same_last_year', 'number_period': 1}
        self._init_filter_comparison(options)
        ctx = self._set_context(options)

        lines = self.with_context(ctx)._get_lines(options)

        ReportLine = self.env['account.financial.html.report.line']
        date_from = fields.Date.from_string(options['date'].get('date_from'))
        date_to = fields.Date.from_string(options['date'].get('date_to'))
        values = {
            '01': {'value': date_from.strftime("%d/%m/%Y"), 'field_type': 'char'},
            '02': {'value': date_to.strftime("%d/%m/%Y"), 'field_type': 'char'},
            '03': {'value': self.env.company.currency_id.name, 'field_type': 'char'}
        }

        # we only need `account.financial.html.report.line` record's IDs and line['id'] could hold account.account
        # record's IDs as well. Such can be identified by `financial_group_line_id` in line dictionary's key. So,
        # below first condition filters those lines and second one filters lines having ID such as `total_*`
        for line in filter(lambda l: 'financial_group_line_id' not in l and isinstance(l.get('id'), int), lines):
            # financial report's `code` would contain alpha-numeric string like `LU_BS_XXX/LU_BSABR_XXX`
            # where characters at last three positions will be digits, hence we split with `_`
            # and build dictionary having `code` as dictionary key
            split_line_code = (ReportLine.browse(line['id']).code or '').split('_') or []
            columns = line['columns']
            # since we have enabled comparison by default, `columns` element will atleast have two dictionary items.
            # First dict will be holding current year's balance and second one will be holding previous year's balance.
            if len(split_line_code) > 1:
                values.update({
                    split_line_code[2]: {'value': _format_amount(columns[0]['no_format_name']), 'field_type': 'number'}, # current year balance
                    str(int(split_line_code[2]) + 1): {'value': _format_amount(columns[1]['no_format_name']), 'field_type': 'number'} # previous year balance
                })

        lu_template_values.update({
            'forms': [{
                'declaration_type': self._get_lu_reports()[self.id],
                'year': date_from.year,
                'period': "1",
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
        content = "\n".join(re.split(r'\n\s*\n', rendered_content.decode("utf-8")))
        self._lu_validate_xml_content(content)

        return "<?xml version='1.0' encoding='UTF-8'?>" + content
