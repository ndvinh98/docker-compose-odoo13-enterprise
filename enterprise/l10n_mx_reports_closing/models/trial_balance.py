# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class MxClosingReportAccountTrial(models.AbstractModel):
    _name = "l10n_mx.trial.closing.report"
    _inherit = "l10n_mx.trial.report"
    _description = "Complete values to get the closing entry report"

    def _get_lines_fourth_level(self, accounts, grouped_accounts, initial_balances, options, comparison_table):
        date_to = fields.Date.from_string(options['date']['date_to'])
        closing_move = self.env['account.move']._get_closing_move(date_to)
        if closing_move:
            accounts_to_show = closing_move.mapped('line_ids.account_id')
            lines_last_period = {}
            for account in accounts:
                lines_last_period[account] = closing_move.line_ids.filtered(lambda l: l.account_id == account)
            return super(MxClosingReportAccountTrial,
                         self.with_context(closing_move=closing_move, accounts_to_show=accounts_to_show,
                                           lines_last_period=lines_last_period)
                         )._get_lines_fourth_level(
                accounts=accounts, grouped_accounts=grouped_accounts,
                initial_balances=initial_balances, options=options,
                comparison_table=comparison_table)

    def _get_cols(self, initial_balances, account, comparison_table, grouped_accounts, extra_data=None):
        cols = [initial_balances.get(account, 0.0)]
        total_periods = 0
        closing_move = self._context.get('closing_move', None)
        accounts_to_show = self._context.get('accounts_to_show', None)
        lines_last_period = self._context.get('lines_last_period', {})
        for period in range(len(comparison_table)):
            amount = grouped_accounts[account][period]['balance']
            cols[0] = cols[0] + (
                amount - sum(lines_last_period[account].mapped('debit')) +
                sum(lines_last_period[account].mapped('credit')))
            total_periods += amount
            cols += [
                (sum(closing_move.line_ids.filtered(
                    lambda line: line.account_id == account).mapped('debit'))) if account in accounts_to_show else 0,
                (sum(closing_move.line_ids.filtered(
                    lambda line: line.account_id == account).mapped('credit'))) if account in accounts_to_show else 0]
        cols += [initial_balances.get(account, 0.0) + total_periods]
        return cols

    def get_report_name(self):
        context = self.env.context
        date_report = fields.datetime.strptime(
            context['date_from'], DEFAULT_SERVER_DATE_FORMAT) if context.get(
                'date_from') else fields.date.today()
        return '%s%s%sBN' % (
            self.env.company.vat or '',
            date_report.year,
            13)

    def get_bce_dict(self, options):
        result = super(MxClosingReportAccountTrial, self).get_bce_dict(options)
        result['month'] = '13'
        return result
