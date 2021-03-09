# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from .builder.comparison import ComparisonBuilder
from .builder.default import DefaultBuilder
from .handler.journals import JournalsHandler
from .handler.periods import PeriodsHandler
from collections import OrderedDict


class AccountConsolidationTrialBalanceReport(models.AbstractModel):
    _name = "account.consolidation.trial_balance_report"
    _description = "Account consolidation trial balance report"
    _inherit = "account.report"

    filter_multi_company = None
    filter_date = None
    filter_comparison = None
    filter_journals = None
    filter_analytic = None
    filter_partner = None
    filter_cash_basis = None
    filter_all_entries = None
    filter_hierarchy = True
    filter_unfold_all = True
    filter_show_zero_balance_accounts = True
    MAX_LINES = None

    # ACTIONS
    def action_open_view_grid(self, options):
        period_id = self._get_selected_period_id()
        AnalysisPeriod = self.env['consolidation.period']
        periods = AnalysisPeriod.search_read([('id', '=', period_id)], ['display_name'])
        period_name = periods[0]['display_name'] if periods and len(periods) == 1 else False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit') + ' ' + (period_name or ''),
            'res_model': 'consolidation.journal.line',
            'view_mode': 'grid,graph,form',
            'view_type': 'grid',
            'views': [
                [self.env.ref('account_consolidation.view_trial_balance_report_grid').id, 'grid'],
                [self.env.ref('account_consolidation.view_trial_balance_report_graph').id, 'graph'],
                [self.env.ref('account_consolidation.consolidation_journal_line_form').id, 'form']
            ],
            'context': {
                'default_period_id': period_id
            },
            'domain': [('period_id', '=', period_id)]
        }

    def action_open_audit(self, options, params=None):
        account_id = params['lineId']
        journal_id = params['id']
        journal = self.env['consolidation.journal'].browse(journal_id)
        company_period = journal.company_period_id
        journal_lines = self.env['consolidation.journal.line'].search([
            ('account_id', '=', account_id),
            ('journal_id', '=', journal_id)
        ])
        if len(journal_lines) == 0:
            return None
        action = self.env.ref('account_consolidation.view_account_move_line_filter').read()[0]
        action.update({
            'context': {
                'search_default_consolidation_journal_line_ids': journal_lines.ids,
                'search_default_group_by_account': 1,
                'group_by': 'account_id',
                'search_default_posted': 1,
                'consolidation_rate': company_period.rate_consolidation if company_period else 0,
                'currencies_are_different': company_period.currencies_are_different if company_period else False,
                'currencies': {
                    'chart': company_period.currency_chart_id.symbol if company_period else None,
                    'company': company_period.currency_company_id.symbol if company_period else None,
                }
            },
            'views': [(self.env.ref('account_consolidation.view_move_line_tree_grouped_general').id, 'list')]
        })
        return action

    # OVERRIDES
    def _get_options(self, previous_options=None):
        current_options = super()._get_options(previous_options)
        base_period = self._get_selected_period()
        handlers = OrderedDict([
            ('periods', PeriodsHandler(self.env)),
            ('consolidation_journals', JournalsHandler(self.env))
        ])
        for key, handler in handlers.items():
            previous_handler_value = previous_options[key] if previous_options else None
            current_options[key] = handler.handle(previous_handler_value, base_period, current_options)
        return current_options

    def _get_columns_name(self, options):
        AnalysisPeriod = self.env['consolidation.period']
        all_period_ids = PeriodsHandler.get_selected_values(options) + [self._get_selected_period_id()]
        selected_periods = AnalysisPeriod.browse(all_period_ids)
        columns = [{'name': '', 'style': 'width:40%'}]
        if len(selected_periods) == 1:
            return columns + self._get_journals_headers(options)
        else:
            periods_columns = [{'name': period.display_name, 'class': 'number'} for period in selected_periods]
            # Add the percentage column
            if len(selected_periods) == 2:
                return columns + periods_columns + [{'name': '%', 'class': 'number'}]
            else:
                return columns + periods_columns

    def _get_journals_headers(self, options):
        journal_ids = JournalsHandler.get_selected_values(options)
        journals = self.env['consolidation.journal'].browse(journal_ids)
        journal_columns = [{'name': self._get_journal_title(j, options), 'class': 'number'} for j in journals]
        return journal_columns + [{'name': _('Total'), 'class': 'number'}]

    def _get_journal_title(self, journal, options):
        journal_name = journal.name
        if journal.company_period_id:
            journal_name = journal.company_period_id.company_name
        if self.env.context.get('print_mode') or options.get('xlsx_mode'):
            return journal_name
        if journal.currencies_are_different and journal.company_period_id:
            cp = journal.company_period_id
            from_currency = cp.currency_chart_id.symbol
            to_currency = journal.originating_currency_id.symbol
            vals = (journal_name,
                    journal.rate_consolidation,
                    from_currency, cp.currency_rate_avg, to_currency,
                    from_currency, cp.currency_rate_end, to_currency)
            return _(
                "%s<br /><span class=\"subtitle\">Conso Rate: %s%%<br />Avg Rate: 1%s = %s%s / End Rate: 1%s = %s%s</span>") % vals
        return _("%s<br /><span class=\"subtitle\">Conso Rate: %s%%</span><br/><br/>") % (
            journal_name, journal.rate_consolidation)

    @api.model
    def _get_report_name(self):
        return _("Trial Balance")

    def _get_reports_buttons(self):
        ap_is_closed = False
        ap_id = self._get_selected_period_id()
        if ap_id:
            ap = self.env['consolidation.period'].browse(ap_id)
            ap_is_closed = ap.state == 'closed'
        buttons = [
            {'name': _('Print Preview'), 'sequence': 1, 'action': 'print_pdf', 'file_export_type': _('PDF')},
            {'name': _('Export (XLSX)'), 'sequence': 2, 'action': 'print_xlsx', 'file_export_type': _('XLSX')}
        ]
        if not ap_is_closed:
            buttons.append({'name': _('Edit'), 'sequence': 10, 'action': 'action_open_view_grid'})
        return buttons

    def _get_templates(self):
        return {
            'main_template': 'account_consolidation.main_template_conso_report',
            'main_table_header_template': 'account_reports.main_table_header',
            'line_template': 'account_consolidation.line_template',
            'footnotes_template': 'account_reports.footnotes_template',
            'search_template': 'account_reports.search_template',
        }

    @api.model
    def _get_lines(self, options, line_id=None):
        selected_aps = self._get_period_ids(options)
        selected_ap = self._get_selected_period()

        # comparison
        if len(selected_aps) > 1:
            builder = ComparisonBuilder(self.env, selected_ap._format_value)
        else:
            journal_ids = JournalsHandler.get_selected_values(options)
            journals = self.env['consolidation.journal'].browse(journal_ids)
            builder = DefaultBuilder(self.env, selected_ap._format_value, journals)
        return builder.get_lines(selected_aps, options, line_id)

    def print_xlsx(self, options):
        options.update({
            'force_periods': self._get_period_ids(options),
            'xlsx_mode': True
        })
        return super().print_xlsx(options)

    def print_pdf(self, options):
        options.update({
            'force_periods': self._get_period_ids(options)
        })
        return super().print_pdf(options)

    def _get_default_analysis_period(self):
        """
        Get the default analysis period, which is the last one when we order by id desc.
        :return: the if of this analysis period
        :rtype: int
        """
        return self.env['consolidation.period'].search_read([], ['id'], limit=1, order="id desc")[0][
            'id']

    # Handling periods
    def _get_period_ids(self, options):
        """
        Get all the period ids (the base period and the comparison ones if any)
        :param options: the options dict
        :type options: dict
        :return: a list containing the period ids
        :rtype: list
        """
        forced_periods = options.get('force_periods', False)
        return forced_periods or PeriodsHandler.get_selected_values(options) + [self._get_selected_period_id()]

    def _get_selected_period_id(self):
        """
        Get the selected period id (the base period)
        :return: the id of the selected period
        :rtype: int
        """
        if not hasattr(self, 'selected_period_id'):
            default_analysis_period = self.env.context.get('default_period_id',
                                                           self.env.context.get('active_id', None))
            if default_analysis_period:
                self.selected_period_id = default_analysis_period
            else:
                self.selected_period_id = self._get_default_analysis_period()
        return self.selected_period_id

    def _get_selected_period(self):
        """
        Get the selected period (the base period)
        :return: the recordset containing the selected period
        """
        if not hasattr(self, 'selected_period'):
            AnalysisPeriod = self.env['consolidation.period']
            self.selected_period = AnalysisPeriod.browse(self._get_selected_period_id())
        return self.selected_period
