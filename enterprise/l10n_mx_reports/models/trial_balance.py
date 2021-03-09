# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree
from lxml.objectify import fromstring
from odoo import models, api, _, fields, tools
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.xml_utils import _check_with_xsd

MX_NS_REFACTORING = {
    'catalogocuentas__': 'catalogocuentas',
    'BCE__': 'BCE',
}

CFDIBCE_TEMPLATE = 'l10n_mx_reports.cfdibalance'
CFDIBCE_XSD = 'l10n_mx_reports/data/xsd/%s/cfdibalance.xsd'
CFDIBCE_XSLT_CADENA = ('l10n_mx_reports/data/xslt/%s'
                       '/BalanzaComprobacion_1_2.xslt')


# TODO: When the module l10n_mx_edi is merged use the method in that module
def create_list_html(array):
    '''Create a html list of error for the chatter.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class MxReportAccountTrial(models.AbstractModel):
    _name = "l10n_mx.trial.report"
    _inherit = "account.coa.report"
    _description = "Mexican Trial Balance Report"

    filter_hierarchy = None

    def _get_reports_buttons(self):
        """Create the buttons to be used to download the required files"""
        buttons = super(MxReportAccountTrial, self)._get_reports_buttons()
        buttons += [{'name': _('Export For SAT (XML)'), 'sequence': 3, 'action': 'print_xml', 'file_export_type': _('SAT XML')}]
        return buttons

    def _get_templates(self):
        """Get this template for better fit of columns"""
        templates = super(MxReportAccountTrial, self)._get_templates()
        templates['main_table_header_template'] = 'l10n_mx_reports.template_coa_table_header'
        return templates

    def _get_columns_name(self, options):
        """Get more specific columns to use in SAT report"""
        columns = [{'name': ''}, {'name': _('Initial Balance'), 'class': 'number'}]
        if options.get('comparison') and options['comparison'].get('periods'):
            for period in options['comparison']['periods']:
                columns += [
                    {'name': _('Debit'), 'class': 'number'},
                    {'name': _('Credit'), 'class': 'number'},
                    ]
        return columns + [
            {'name': _('Debit'), 'class': 'number'},
            {'name': _('Credit'), 'class': 'number'},
            {'name': _('Total'), 'class': 'number'},
        ]

    def _post_process(self, grouped_accounts, initial_balances, options, comparison_table):
        afrl_obj = self.env['account.financial.html.report.line']
        lines = []
        n_cols = len(comparison_table) * 2 + 2
        total = [0.0] * n_cols
        afr_lines = afrl_obj.search([
            ('parent_id', '=', False),
            ('code', 'ilike', 'MX_COA_%')], order='code')
        for line in afr_lines:
            childs = self._get_lines_second_level(
                line.children_ids, grouped_accounts, initial_balances, options, comparison_table)
            if not childs:
                continue
            cols = ['']
            if not options.get('coa_only'):
                cols = cols * n_cols
                child_cols = [c['columns'] for c in childs if c.get('level') == 2]
                total_line = []
                for col in range(n_cols):
                    total_line += [sum(a[col] for a in child_cols)]
                    total[col] += total_line[col]
                for child in childs:
                    child['columns'] = [{'name': self.format_value(v)} for v in child['columns']]
            lines.append({
                'id': 'hierarchy_' + line.code,
                'name': line.name,
                'columns': [{'name': v} for v in cols],
                'level': 1,
                'unfoldable': False,
                'unfolded': True,
            })
            lines.extend(childs)
            if not options.get('coa_only'):
                lines.append({
                    'id': 'total_%s' % line.code,
                    'name': _('Total %s') % line.name[2:],
                    'level': 0,
                    'class': 'hierarchy_total',
                    'columns': [{'name': self.format_value(v)} for v in total_line],
                })
        if not options.get('coa_only'):
            lines.append({
                'id': 'hierarchy_total',
                'name': _('Total'),
                'level': 0,
                'class': 'hierarchy_total',
                'columns': [{'name': self.format_value(v)} for v in total],
            })
        return lines

    @api.model
    def _get_lines_second_level(self, lines_child, grouped_accounts,
                                initial_balances, options, comparison_table):
        """Return list of tags found in the second level"""
        lines = []
        sorted_childs = sorted(lines_child, key=lambda a: a.name)
        for child in sorted_childs:
            account_lines = self._get_lines_third_level(
                child, grouped_accounts, initial_balances, options,
                comparison_table)
            if not account_lines:
                continue
            cols = [{'name': ''}]
            if not options.get('coa_only'):
                n_cols = len(comparison_table) * 2 + 2
                child_cols = [c['columns'] for c in account_lines if c.get('level') == 3]
                cols = []
                for col in range(n_cols):
                    cols += [sum(a[col] for a in child_cols)]
            lines.append({
                'id': 'level_one_%s' % child.id,
                'name': child.name,
                'columns': cols,
                'level': 2,
                'class': 'hierarchy_total' if not options.get('coa_only') else '',
                'unfoldable': True,
                'unfolded': True,
            })
            lines.extend(account_lines)
        return lines

    @api.model
    def _get_lines_third_level(self, line, grouped_accounts, initial_balances,
                               options, comparison_table):
        """Return list of accounts found in the third level"""
        lines = []
        domain = safe_eval(line.domain or '[]')
        domain += [
            ('company_id', 'in', self.env.context['company_ids']),
        ]
        basis_account_ids = self.env['account.tax'].search_read(
            [('cash_basis_base_account_id', '!=', False)], ['cash_basis_base_account_id'])
        basis_account_ids = [account['cash_basis_base_account_id'][0] for account in basis_account_ids]
        domain.append((('id', 'not in', basis_account_ids)))
        account_ids = self.env['account.account'].search(domain, order='code')
        tags = account_ids.mapped('tag_ids').filtered(
            lambda r: r.color == 4).sorted(key=lambda a: a.name)
        for tag in tags:
            accounts = account_ids.search([
                ('tag_ids', 'in', [tag.id]),
                ('id', 'in', account_ids.ids),
            ])
            name = tag.name
            name = name[:63] + "..." if len(name) > 65 else name
            cols = [{'name': ''}]
            childs = self._get_lines_fourth_level(accounts, grouped_accounts, initial_balances, options, comparison_table)
            if not childs:
                continue
            if not options.get('coa_only'):
                n_cols = len(comparison_table) * 2 + 2
                child_cols = [c['columns'] for c in childs]
                cols = []
                for col in range(n_cols):
                    cols += [sum(a[col] for a in child_cols)]
            lines.append({
                'id': 'level_two_%s' % tag.id,
                'parent_id': 'level_one_%s' % line.id,
                'name': name,
                'columns': cols,
                'level': 3,
                'unfoldable': True,
                'unfolded': True,
                'tag_id': tag.id,
            })
            lines.extend(childs)
        return lines

    def _get_lines_fourth_level(self, accounts, grouped_accounts, initial_balances, options, comparison_table):
        lines = []
        company_id = self.env.context.get('company_id') or self.env.company
        is_zero = company_id.currency_id.is_zero
        for account in accounts:
            # skip accounts with all periods = 0 (debit and credit) and no initial balance
            if not options.get('coa_only'):
                non_zero = False
                for period in range(len(comparison_table)):
                    if account in grouped_accounts and (
                        not is_zero(initial_balances.get(account, 0)) or
                        not is_zero(grouped_accounts[account][period]['debit']) or
                        not is_zero(grouped_accounts[account][period]['credit'])
                    ):
                        non_zero = True
                        break
                if not non_zero:
                    continue
            name = account.code + " " + account.name
            name = name[:63] + "..." if len(name) > 65 else name
            tag = account.tag_ids.filtered(lambda r: r.color == 4)
            if len(tag) > 1:
                raise UserError(_(
                    'The account %s is incorrectly configured. Only one tag is allowed.'
                ) % account.name)
            nature = dict(tag.fields_get()['nature']['selection']).get(tag.nature, '')
            cols = [{'name': nature}]
            if not options.get('coa_only'):
                cols = self._get_cols(initial_balances, account, comparison_table, grouped_accounts)
            lines.append({
                'id': account.id,
                'parent_id': 'level_two_%s' % tag.id,
                'name': name,
                'level': 4,
                'columns': cols,
                'caret_options': 'account.account',
            })
        return lines

    def _get_cols(self, initial_balances, account, comparison_table, grouped_accounts):
        cols = [initial_balances.get(account, 0.0)]
        total_periods = 0
        for period in range(len(comparison_table)):
            amount = grouped_accounts[account][period]['balance']
            total_periods += amount
            cols += [grouped_accounts[account][period]['debit'],
                        grouped_accounts[account][period]['credit']]
        cols += [initial_balances.get(account, 0.0) + total_periods]
        return cols

    def _l10n_mx_edi_add_digital_stamp(self, path_xslt, cfdi):
        """Add digital stamp certificate attributes in XML report"""
        company_id = self.env.company
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            return cfdi
        tree = fromstring(cfdi)
        xslt_root = etree.parse(tools.file_open(path_xslt))
        cadena = str(etree.XSLT(xslt_root)(tree))
        sello = certificate_id.sudo().get_encrypted_cadena(cadena)
        tree.attrib['Sello'] = sello
        tree.attrib['noCertificado'] = certificate_id.serial_number
        tree.attrib['Certificado'] = certificate_id.sudo().get_data()[0]
        return etree.tostring(tree, pretty_print=True,
                              xml_declaration=True, encoding='UTF-8')

    def get_bce_dict(self, options):
        company = self.env.company
        xml_data = self._get_lines(options)
        accounts = []
        account_lines = [l for l in xml_data
                         if l.get('level') in [2, 3] and l.get('show', True)]
        for line in account_lines:
            cols = line.get('columns', [])
            initial, debit, credit, end = (
                cols[0].get('name', 0.0),
                cols[-3].get('name', 0.0),
                cols[-2].get('name', 0.0),
                cols[-1].get('name', 0.0))
            accounts.append({
                'number': line.get('name').split(' ', 1)[0],
                'initial': "%.2f" % (initial),
                'debit': "%.2f" % (debit),
                'credit': "%.2f" % (credit),
                'end': "%.2f" % (end),
            })
        date = fields.Date.from_string(self.env.context['date_from'])
        chart = {
            'vat': company.vat or '',
            'month': str(date.month).zfill(2),
            'year': date.year,
            'accounts': accounts,
            'type': 'N',
        }
        return chart

    @api.model
    def _get_lines(self, options, line_id=None):
        # Create new options with 'unfold_all' to compute the initial balances.
        # Then, the '_do_query' will compute all sums/unaffected earnings/initial balances for all comparisons.
        new_options = options.copy()
        new_options['unfold_all'] = True
        options_list = self._get_options_periods_list(new_options)
        accounts_results, taxes_results = self.env['account.general.ledger']._do_query(options_list, fetch_lines=False)

        grouped_accounts = {}
        initial_balances = {}
        comparison_table = [options.get('date')]
        comparison_table += options.get('comparison') and options['comparison'].get('periods') or []
        for account, periods_results in accounts_results:
            grouped_accounts.setdefault(account, [])
            periods_results.reverse()
            for i, res in enumerate(periods_results):
                account_init_bal = res.get('initial_balance', {})
                if i == 0:
                    initial_balances[account] = res.get('initial_balance', {}).get('balance', 0.0)
                sums = [
                    res.get('sum', {}).get('debit', 0.0) - account_init_bal.get('debit', 0.0),
                    res.get('sum', {}).get('credit', 0.0) - account_init_bal.get('credit', 0.0),
                ]
                grouped_accounts[account].append({
                    'balance': sums[0] - sums[1],
                    'debit': sums[0],
                    'credit': sums[1],
                })

        return self._post_process(grouped_accounts, initial_balances, options, comparison_table)

    @api.model
    def get_xml(self, options):
        qweb = self.env['ir.qweb']
        version = '1.3'
        ctx = self._set_context(options)
        if not ctx.get('date_to'):
            return False
        ctx['no_format'] = True
        values = self.with_context(ctx).get_bce_dict(options)
        cfdicoa = qweb.render(CFDIBCE_TEMPLATE, values=values)
        for key, value in MX_NS_REFACTORING.items():
            cfdicoa = cfdicoa.replace(key.encode('UTF-8'),
                                      value.encode('UTF-8') + b':')
        cfdicoa = self._l10n_mx_edi_add_digital_stamp(
            CFDIBCE_XSLT_CADENA % version, cfdicoa)

        with tools.file_open(CFDIBCE_XSD % version, "rb") as xsd:
            _check_with_xsd(cfdicoa, xsd)
        return cfdicoa

    def get_html(self, options, line_id=None, additional_context=None):
        return super(MxReportAccountTrial, self.with_context(
            self._set_context(options))).get_html(
                options, line_id, additional_context)

    def get_report_filename(self, options):
        return super(MxReportAccountTrial, self.with_context(
            self._set_context(options))).get_report_filename(options).upper()

    def _get_report_name(self):
        """The structure to name the Trial Balance reports is:
        VAT + YEAR + MONTH + ReportCode
        ReportCode:
        BN - Trial balance with normal information
        BC - Trial balance with with complementary information. (Now is
        not suportes)"""
        context = self.env.context
        date_report = fields.Date.from_string(context['date_from']) if context.get(
                'date_from') else fields.Date.today()
        return '%s%s%sBN' % (
            self.env.company.vat or '',
            date_report.year,
            str(date_report.month).zfill(2))

    def open_journal_items(self, options, params):
        new_params = params.copy()
        new_params.pop('financial_group_line_id', False)
        return super(MxReportAccountTrial, self).open_journal_items(
            options, new_params)

    def view_all_journal_items(self, options, params):
        if not params.get('id') or 'hierarchy' in params.get('id'):
            return super(MxReportAccountTrial, self).view_all_journal_items(
                options, params)
        ctx = self._set_context(options)
        lines = self.with_context(**ctx)._get_lines(options)
        new_params = params.copy()
        new_params.pop('id', False)
        accounts = self._get_accounts_journal_items([params.get('id')], lines)
        ctx = {'search_default_account': 1}
        res = super(MxReportAccountTrial, self.with_context(
            **ctx)).view_all_journal_items(options, new_params)
        res.get('domain', []).append(('account_id', 'in', accounts))
        return res

    def _get_accounts_journal_items(self, params, lines):
        levels = [
            l.get('level') for l in lines if l.get('parent_id') in params]
        if levels and levels[0] == 4:
            return [
                l.get('id') for l in lines if l.get('parent_id') in params]
        params = [
            l.get('id') for l in lines if l.get('parent_id') in params]
        return self._get_accounts_journal_items(params, lines)

    def _set_context(self, options):
        ctx = super(MxReportAccountTrial, self)._set_context(options)
        ctx['model'] = self._name
        return ctx
