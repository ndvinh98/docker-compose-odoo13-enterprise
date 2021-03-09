# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import re


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('line_ids', 'invoice_payment_term_id', 'invoice_date_due', 'invoice_cash_rounding_id', 'invoice_vendor_bill_id')
    def _onchange_recompute_dynamic_lines(self):
        # OVERRIDE
        to_predict_lines = self.line_ids.filtered(lambda line: line.predict_from_name)
        for line in to_predict_lines:
            line.predict_from_name = False

            # Predict product.
            if self.env.user.has_group('account.group_products_in_bills') and not line.product_id:
                predicted_product_id = line._predict_product(line.name)
                if predicted_product_id and predicted_product_id != line.product_id.id:
                    line['product_id'] = predicted_product_id
                    line._onchange_product_id()
                    line.recompute_tax_line = True

            # Predict account.
            if not line.account_id or line.predict_override_default_account:
                predicted_account_id = line._predict_account(line.name, line.partner_id)
                if predicted_account_id and predicted_account_id != line.account_id.id:
                    line['account_id'] = predicted_account_id
                    line._onchange_account_id()
                    line.recompute_tax_line = True

            line.predict_override_default_account = False
        return super(AccountMove, self)._onchange_recompute_dynamic_lines()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    predict_from_name = fields.Boolean(store=False,
        help="Technical field used to know on which lines the prediction must be done.")
    predict_override_default_account = fields.Boolean(store=False)

    def _get_predict_postgres_dictionary(self):
        lang = self._context.get('lang') and self._context.get('lang')[:2]
        return {'fr': 'french'}.get(lang, 'english')

    def _predict_field(self, sql_query, description):
        psql_lang = self._get_predict_postgres_dictionary()
        parsed_description = re.sub(r"[*&()|!':<>=%/~@,.;$\[\]]+", " ", description)
        parsed_description = ' | '.join(parsed_description.split())
        limit_parameter = self.env["ir.config_parameter"].sudo().get_param("account.bill.predict.history.limit", '10000')
        params = {
            'lang': psql_lang,
            'description': parsed_description,
            'company_id': self.move_id.journal_id.company_id.id or self.env.company.id,
            'limit_parameter': int(limit_parameter),
        }
        try:
            self.env.cr.execute(sql_query, params)
            result = self.env.cr.fetchone()
            if result:
                return result[1]
        except Exception as e:
            # In case there is an error while parsing the to_tsquery (wrong character for example)
            # We don't want to have a traceback, instead return False
            return False
        return False

    def _predict_product(self, description):
        if not description:
            return False

        sql_query = """
            SELECT
                max(f.rel) AS ranking,
                f.product_id,
                count(coalesce(f.product_id, 1)) AS count
            FROM (
                SELECT
                    p_search.product_id,
                    ts_rank(p_search.document, query_plain) AS rel
                FROM (
                    SELECT
                        ail.product_id,
                        (setweight(to_tsvector(%(lang)s, ail.name), 'B'))
                         AS document
                    FROM account_move_line ail
                    JOIN account_move inv
                        ON ail.move_id = inv.id

                    WHERE inv.type = 'in_invoice'
                        AND inv.state = 'posted'
                        AND ail.display_type IS NULL
                        AND NOT ail.exclude_from_invoice_tab
                        AND ail.company_id = %(company_id)s
                    ORDER BY inv.invoice_date DESC
                    LIMIT %(limit_parameter)s
                ) p_search,
                to_tsquery(%(lang)s, %(description)s) query_plain
                WHERE (p_search.document @@ query_plain)
            ) AS f
            GROUP BY f.product_id
            ORDER BY ranking desc, count desc
        """
        return self._predict_field(sql_query, description)

    def _predict_account(self, description, partner):
        # This method uses postgres tsvector in order to try to deduce the account_id of an invoice line
        # based on the text entered into the name (description) field.
        # We give some more weight to search with the same partner_id (roughly 20%) in order to have better result
        # We only limit the search on the previous 10000 entries, which according to our tests bore the best
        # results. However this limit parameter is configurable by creating a config parameter with the key:
        # account.bill.predict.history.limit

        # For information, the tests were executed with a dataset of 40 000 bills from a live database, We splitted
        # the dataset in 2, removing the 5000 most recent entries and we tried to use this method to guess the account
        # of this validation set based on the previous entries.
        # The result is roughly 90% of success.
        if not description or not partner:
            return False

        sql_query = """
            SELECT
                max(f.rel) AS ranking,
                f.account_id,
                count(f.account_id) AS count
            FROM (
                SELECT
                    p_search.account_id,
                    ts_rank(p_search.document, query_plain) AS rel
                FROM (
                    (SELECT
                        ail.account_id,
                        (setweight(to_tsvector(%(lang)s, ail.name), 'B')) ||
                        (setweight(to_tsvector('simple', 'partnerid'|| replace(ail.partner_id::text, '-', 'x')), 'A')) AS document
                    FROM account_move_line ail
                    JOIN account_move inv
                        ON ail.move_id = inv.id
                    WHERE inv.type = 'in_invoice'
                        AND inv.state = 'posted'
                        AND ail.display_type IS NULL
                        AND NOT ail.exclude_from_invoice_tab
                        AND ail.company_id = %(company_id)s
                    ORDER BY inv.invoice_date DESC
                    LIMIT %(limit_parameter)s
                    ) UNION ALL (
                    SELECT
                        id as account_id,
                        (setweight(to_tsvector(%(lang)s, name), 'B')) AS document
                    FROM account_account
                    WHERE user_type_id IN (
                        SELECT id
                        FROM account_account_type
                        WHERE internal_group = 'expense')
                        AND company_id = %(company_id)s
                    )
                ) p_search,
                to_tsquery(%(lang)s, %(description)s) query_plain
                WHERE (p_search.document @@ query_plain)
            ) AS f
            GROUP BY f.account_id
            ORDER BY ranking desc, count desc
        """
        description += ' partnerid' + str(partner.id or '').replace('-', 'x')
        return self._predict_field(sql_query, description)

    @api.onchange('name')
    def _onchange_enable_predictive(self):
        if self.move_id.type == 'in_invoice' and self.name and not self.display_type:
            self.predict_from_name = True

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # OVERRIDE
        # Don't predict the account if computed from the product.
        res = super()._onchange_product_id()

        if self.product_id and self.account_id:
            self.predict_override_default_account = False

        return res

    @api.model
    def default_get(self, default_fields):
        # OVERRIDE
        # Add a flag meant to predict the account when the move.line change.
        # Don't set a default account. Let the prediction do this job.
        values = super(AccountMoveLine, self).default_get(default_fields)
        if 'account_id' in default_fields and values.get('account_id'):
            values['predict_override_default_account'] = True
        return values
