# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _, fields, tools
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.xml_utils import _check_with_xsd

MX_NS_REFACTORING = {
    'catalogocuentas__': 'catalogocuentas',
    'BCE__': 'BCE',
}

CFDICOA_TEMPLATE = 'l10n_mx_reports.cfdicoa'
CFDICOA_XSD = 'l10n_mx_reports/data/xsd/%s/cfdicoa.xsd'
CFDICOA_XSLT_CADENA = 'l10n_mx_reports/data/xslt/%s/CatalogoCuentas_1_2.xslt'


class MXReportAccountCoa(models.AbstractModel):
    _name = "l10n_mx.coa.report"
    _inherit = "l10n_mx.trial.report"
    _description = "Mexican Chart of Account Report"

    filter_comparison = None
    filter_cash_basis = None
    filter_all_entries = None
    filter_hierarchy = None
    filter_journals = None

    def _get_templates(self):
        templates = super(MXReportAccountCoa, self)._get_templates()
        #use the main template instead of the trial balance with 2 header lines
        templates['main_table_header_template'] = 'account_reports.main_table_header'
        templates['main_template'] = 'account_reports.main_template'
        return templates

    def _get_columns_name(self, options):
        return [{'name': ''}, {'name': _('Nature')}]

    def _get_lines(self, options, line_id=None):
        options['coa_only'] = True
        lines = self._post_process({}, {}, options, [])
        if lines:
            afrl_obj = self.env['account.financial.html.report.line']
            afr_lines = afrl_obj.search([
                ('parent_id', '=', False),
                ('code', 'ilike', 'MX_COA_%')], order='code')
            lines.extend(self._get_accounts_not_found(afr_lines))
        return lines

    def _get_accounts_not_found(self, afr_lines):
        """Add the accounts that are not found with domains in the AFR
        lines, with this the is indicated the accounts that will not show in
        the report."""
        accounts = []
        lines = []
        account_obj = self.env['account.account']
        for domain in afr_lines.mapped('children_ids').mapped('domain'):
            account_ids = account_obj.search(
                safe_eval(domain or '[]'), order='code')
            accounts.extend(account_ids.ids)
        basis_account_ids = self.env['account.tax'].search_read(
            [('cash_basis_base_account_id', '!=', False)], ['cash_basis_base_account_id'])
        accounts.extend([account['cash_basis_base_account_id'][0] for account in basis_account_ids])
        accounts = account_obj.search([
            ('id', 'not in', list(set(accounts))),
            ('deprecated', '=', False),
            ('company_id', 'in', self.env.context['company_ids']),
        ])

        if accounts:
            lines.append({
                'id': 'misconfigured_accounts',
                'type': 'line',
                'name': _('Misconfigured Accounts'),
                'footnotes': {},
                'columns': [{'name': ''}],
                'level': 1,
                'unfoldable': False,
                'unfolded': True,
            })
            for account in accounts:
                name = '%s %s' % (account.code, account.name)
                name = name[:133] + "..." if len(name) > 135 else name
                lines.append({
                    'id': account.id,
                    'type': 'account_id',
                    'name': name,
                    'footnotes': {},
                    'columns': [{'name': ''}],
                    'level': 3,
                    'caret_options': 'account.account',
                    'unfoldable': False,
                    'unfolded': True,
                })
        return lines

    def _get_coa_dict(self, options):
        xml_data = self._get_lines(options)
        accounts = []
        account_lines = [l for l in xml_data
                         if l.get('level') in [2, 3]]
        tag_obj = self.env['account.account.tag']
        for line in account_lines:
            if line.get('level') == 2:
                parent = line
                print_parent = True
                continue
            tag_id = line.get('tag_id', False)
            tag = tag_obj.browse(tag_id)
            if not tag:
                msg = _(
                    'This XML could not be generated because some accounts '
                    'are not correctly configured and can not be added in '
                    'this report. This accounts are found in the section '
                    '"Misconfigured Accounts", please configure your tag and '
                    'try generate the report XML again.')
                raise ValidationError(msg)
            if print_parent:
                name = parent.get('name').split(' ', 1)
                accounts.append({
                    'code': name[0],
                    'number': name[0],
                    'name': name[-1],
                    'level': '1',
                    'nature': tag.nature
                })
                print_parent = False
            name = line.get('name').split(' ', 1)
            accounts.append({
                'code': name[0],
                'number': name[0],
                'name': name[-1],
                'level': '2',
                'nature': tag.nature,
            })
        ctx = self._set_context(options)
        date = fields.Date.from_string(ctx['date_from'])
        chart = {
            'vat': self.env.company.vat or '',
            'month': str(date.month).zfill(2),
            'year': date.year,
            'accounts': accounts
        }
        return chart

    def get_xml(self, options):
        qweb = self.env['ir.qweb']
        version = '1.3'
        ctx = self._set_context(options)
        values = self.with_context(ctx)._get_coa_dict(options)
        cfdicoa = qweb.render(CFDICOA_TEMPLATE, values=values)
        for key, value in MX_NS_REFACTORING.items():
            cfdicoa = cfdicoa.replace(key.encode('UTF-8'),
                                      value.encode('UTF-8') + b':')
        cfdicoa = self._l10n_mx_edi_add_digital_stamp(
            CFDICOA_XSLT_CADENA % version, cfdicoa)

        with tools.file_open(CFDICOA_XSD % version, "rb") as xsd:
            _check_with_xsd(cfdicoa, xsd)
        return cfdicoa

    def _get_report_name(self):
        """The structure to name the CoA reports is:
        VAT + YEAR + MONTH + CT"""
        context = self.env.context
        date_report = fields.Date.from_string(context['date_from']) if context.get(
                'date_from') else fields.date.today()
        return '%s%s%sCT' % (
            self.env.company.vat or '',
            date_report.year,
            str(date_report.month).zfill(2))
