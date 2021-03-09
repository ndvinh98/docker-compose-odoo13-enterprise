# -*- coding: utf-8 -*-

from odoo import models, api, _


class ReportCheckRegister(models.AbstractModel):
    '''Check Register is an accounting report usually part of the general ledger, used to record
    financial transactions in cash.
    '''
    _name = 'l10n_us_reports.check.register'
    _description = 'Check Register Report'
    _inherit = 'account.general.ledger'

    filter_cash_basis = None

    def _get_filter_journals(self):
        #filter only the bank/cash/miscellaneous journals
        return self.env['account.journal'].search([
            ('company_id', 'in', self.env.companies.ids or [self.env.company.id]),
            ('type', 'in', ['bank', 'cash', 'general'])], order="company_id, name")

    @api.model
    def _l10n_us_reports_liquidity_accounts(self):
        '''Retrieve the liquidity accounts part of the check register reports.

        :return: The liquidity account.account records.
        '''
        liquidity_type_id = self.env.ref('account.data_account_type_liquidity')
        return self.env['account.account'].search([('user_type_id', '=', liquidity_type_id.id)])

    @api.model
    def _get_lines(self, options, line_id=None):
        # Override to filter liquidity accounts using the context
        liquidity_account_ids = self._l10n_us_reports_liquidity_accounts()
        context = dict(self._context, account_ids=liquidity_account_ids)
        return super(ReportCheckRegister, self.with_context(context))._get_lines(options, line_id=line_id)

    @api.model
    def _get_report_name(self):
        '''Override to change the report name.
        '''
        return _('Check Register')
