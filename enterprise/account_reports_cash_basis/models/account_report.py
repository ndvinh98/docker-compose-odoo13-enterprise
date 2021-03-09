# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _

import re

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    filter_cash_basis = None

    @api.model
    def _prepare_lines_for_cash_basis(self, options):
        """Prepare the temp_account_move_line substitue.

        This method should be used once before all the SQL queries using the
        table account_move_line for reports in cash basis.
        It will create a new table like the account_move_line table, but with
        amounts and the date relative to the cash basis.
        """
        if options.get('cash_basis'):
            self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='account_move_line'")
            changed_fields = ['date', 'amount_currency', 'amount_residual', 'balance', 'debit', 'credit']
            unchanged_fields = list(set(f[0] for f in self.env.cr.fetchall()) - set(changed_fields))
            selected_journals = tuple(journal['id'] for journal in self._get_options_journals(options))
            sql = """   -- Create a temporary table
                CREATE TEMPORARY TABLE IF NOT EXISTS temp_account_move_line () INHERITS (account_move_line) ON COMMIT DROP;

                INSERT INTO temp_account_move_line ({all_fields}) SELECT
                    {unchanged_fields},
                    "account_move_line".date,
                    "account_move_line".amount_currency,
                    "account_move_line".amount_residual,
                    "account_move_line".balance,
                    "account_move_line".debit,
                    "account_move_line".credit
                FROM ONLY account_move_line
                WHERE (
                    "account_move_line".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                    OR "account_move_line".move_id NOT IN (
                        SELECT DISTINCT aml.move_id
                        FROM ONLY account_move_line aml
                        JOIN account_account account ON aml.account_id = account.id
                        WHERE account.internal_type IN ('receivable', 'payable')
                    )
                )
                {where_journals};

                WITH payment_table AS (
                    SELECT aml.move_id, aml2.date,
                        CASE WHEN (aml.balance = 0 OR sub_aml.total_per_account = 0)
                            THEN 0
                            ELSE part.amount / ABS(sub_aml.total_per_account)
                        END as matched_percentage
                    FROM account_partial_reconcile part
                    JOIN ONLY account_move_line aml ON aml.id = part.debit_move_id OR aml.id = part.credit_move_id
                    JOIN ONLY account_move_line aml2 ON
                        (aml2.id = part.credit_move_id OR aml2.id = part.debit_move_id)
                        AND aml.id != aml2.id
                    JOIN (
                        SELECT move_id, account_id, ABS(SUM(balance)) AS total_per_account
                        FROM ONLY account_move_line
                        GROUP BY move_id, account_id
                    ) sub_aml ON (aml.account_id = sub_aml.account_id AND aml.move_id=sub_aml.move_id)
                    JOIN account_account account ON aml.account_id = account.id
                    WHERE account.internal_type IN ('receivable', 'payable')
                )
                INSERT INTO temp_account_move_line ({all_fields}) SELECT
                    {unchanged_fields},
                    ref.date,
                    ref.matched_percentage * "account_move_line".amount_currency,
                    ref.matched_percentage * "account_move_line".amount_residual,
                    ref.matched_percentage * "account_move_line".balance,
                    ref.matched_percentage * "account_move_line".debit,
                    ref.matched_percentage * "account_move_line".credit
                FROM payment_table ref
                JOIN ONLY account_move_line ON "account_move_line".move_id = ref.move_id
                WHERE NOT (
                    "account_move_line".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                    OR "account_move_line".move_id NOT IN (
                        SELECT DISTINCT aml.move_id
                        FROM ONLY account_move_line aml
                        JOIN account_account account ON aml.account_id = account.id
                        WHERE account.internal_type IN ('receivable', 'payable')
                    )
                )
                {where_journals};
            """.format(
                all_fields=', '.join(unchanged_fields + changed_fields),
                unchanged_fields=', '.join(['"account_move_line".' + f for f in unchanged_fields]),
                where_journals=selected_journals and 'AND "account_move_line".journal_id IN %(journal_ids)s' or ''
            )
            params = {
                'journal_ids': selected_journals,
            }
            self.env.cr.execute(sql, params)

    def _set_context(self, options):
        ctx = super()._set_context(options)
        if options.get('cash_basis'):
            ctx['cash_basis'] = True
        return ctx

    @api.model
    def _prepare_query_for_cash_basis(self, query):
        """Substitute the table account_move_line for cash basis mode.

        This method should be used to alter every SQL query using the table
        account_move_line for reports in cash basis.
        """
        if self.env.context.get('cash_basis'):
            query = re.sub(r'\baccount_move_line\b', 'temp_account_move_line', query)
        return query

class AccountChartOfAccountReport(models.AbstractModel):
    _inherit = "account.coa.report"

    filter_cash_basis = False

    def _get_lines(self, options, line_id=False):
        self._prepare_lines_for_cash_basis(options)
        return super()._get_lines(options, line_id)


class ReportGeneralLedger(models.AbstractModel):
    _inherit = "account.general.ledger"

    filter_cash_basis = False

    def _get_lines(self, options, line_id=False):
        self._prepare_lines_for_cash_basis(options)
        return super()._get_lines(options, line_id)

    def _get_query_sums(self, options_list, expanded_account=None):
        query, params = super()._get_query_sums(options_list, expanded_account)
        return self._prepare_query_for_cash_basis(query), params

    def _get_query_amls(self, options, expanded_account, offset=None, limit=None):
        query, params = super()._get_query_amls(options, expanded_account, offset, limit)
        return self._prepare_query_for_cash_basis(query), params


class ReportAccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"

    cash_basis = fields.Boolean('Allow cash basis mode', help='display the option to switch to cash basis mode')

    @property
    def filter_cash_basis(self):
        return False if self.cash_basis else None

    def _get_lines(self, options, line_id=False):
        self._prepare_lines_for_cash_basis(options)
        return super()._get_lines(options, line_id)


class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    def _build_query_rows_count(self, groupby, tables, where_clause, params):
        query, params = super()._build_query_rows_count(groupby, tables, where_clause, params)
        return self.env['account.report']._prepare_query_for_cash_basis(query), params

    def _build_query_compute_line(self, select, tables, where_clause, params):
        query, params = super()._build_query_compute_line(select, tables, where_clause, params)
        return self.env['account.report']._prepare_query_for_cash_basis(query), params

    def _build_query_eval_formula(self, groupby, select, tables, where_clause, params):
        query, params = super()._build_query_eval_formula(groupby, select, tables, where_clause, params)
        return self.env['account.report']._prepare_query_for_cash_basis(query), params
