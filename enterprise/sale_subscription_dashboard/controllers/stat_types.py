# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo.http import request
from odoo import _lt


def _execute_sql_query(fields, tables, conditions, query_args, filters, groupby=None):
    """ Returns the result of the SQL query. """
    query, args = _build_sql_query(fields, tables, conditions, query_args, filters, groupby=groupby)
    request.cr.execute(query, args)
    return request.cr.dictfetchall()


def _build_sql_query(fields, tables, conditions, query_args, filters, groupby=None):
    """ The goal of this function is to avoid:
        * writing raw SQL requests (kind of abstraction)
        * writing additionnal conditions for filters (same conditions for every request)
    :params fields, tables, conditions: basic SQL request statements
    :params query_args: dict of optional query args used in the request
    :params filters: dict of optional filters (template_ids, tag_ids, company_ids)
    :params groupby: additionnal groupby statement

    :returns: the SQL request and the new query_args (with filters tables & conditions)
    """
    # The conditions should use named arguments and these arguments are in query_args.

    if filters.get('template_ids'):
        tables.append("sale_subscription")
        conditions.append("account_move_line.subscription_id = sale_subscription.id")
        conditions.append("sale_subscription.template_id IN %(template_ids)s")
        query_args['template_ids'] = tuple(filters.get('template_ids'))

    if filters.get('sale_team_ids'):
        tables.append("crm_team")
        conditions.append("account_move.team_id = crm_team.id")
        conditions.append("crm_team.id IN %(team_ids)s")
        query_args['team_ids'] = tuple(filters.get('sale_team_ids'))

    if filters.get('tag_ids'):
        tables.append("sale_subscription")
        tables.append("account_analytic_tag_sale_subscription_rel")
        conditions.append("account_move_line.subscription_id = sale_subscription.id")
        conditions.append("sale_subscription.id = account_analytic_tag_sale_subscription_rel.sale_subscription_id")
        conditions.append("account_analytic_tag_sale_subscription_rel.account_analytic_tag_id IN %(tag_ids)s")
        query_args['tag_ids'] = tuple(filters.get('tag_ids'))

    if filters.get('company_ids'):
        conditions.append("account_move.company_id IN %(company_ids)s")
        conditions.append("account_move_line.company_id IN %(company_ids)s")
        query_args['company_ids'] = tuple(filters.get('company_ids'))

    fields_str = ', '.join(set(fields))
    tables_str = ', '.join(set(tables))
    conditions_str = ' AND '.join(set(conditions))

    if groupby:
        base_query = "SELECT %s FROM %s WHERE %s GROUP BY %s" % (fields_str, tables_str, conditions_str, groupby)
    else:
        base_query = "SELECT %s FROM %s WHERE %s" % (fields_str, tables_str, conditions_str)

    return base_query, query_args


def compute_net_revenue(start_date, end_date, filters):
    fields = ['SUM(account_move_line.price_subtotal)']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "account_move.invoice_date BETWEEN %(start_date)s AND %(end_date)s",
        "account_move_line.move_id = account_move.id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'start_date': start_date,
        'end_date': end_date,
    }, filters)

    return 0 if not sql_results or not sql_results[0]['sum'] else int(sql_results[0]['sum'])


def compute_arpu(start_date, end_date, filters):
    mrr = compute_mrr(start_date, end_date, filters)
    nb_customers = compute_nb_contracts(start_date, end_date, filters)
    result = 0 if not nb_customers else mrr/float(nb_customers)
    return int(result)


def compute_arr(start_date, end_date, filters):
    result = 12*compute_mrr(start_date, end_date, filters)
    return int(result)


def compute_ltv(start_date, end_date, filters):
    fields = ['CASE WHEN COUNT(DISTINCT account_move_line.subscription_id)!=0 THEN SUM(account_move_line.subscription_mrr)/COUNT(DISTINCT account_move_line.subscription_id) ELSE 0 END AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')"
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    avg_mrr_per_customer = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']
    logo_churn = compute_logo_churn(start_date, end_date, filters)
    result = 0 if logo_churn == 0 else avg_mrr_per_customer/float(logo_churn)
    return int(result)


def compute_nrr(start_date, end_date, filters):
    fields = ['SUM(account_move_line.price_subtotal)']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "(account_move.invoice_date BETWEEN %(start_date)s AND %(end_date)s)",
        "account_move_line.move_id = account_move.id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_start_date IS NULL",
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'start_date': start_date,
        'end_date': end_date,
    }, filters)

    return 0 if not sql_results or not sql_results[0]['sum'] else int(sql_results[0]['sum'])


def compute_nb_contracts(start_date, end_date, filters):
    fields = ['COUNT(DISTINCT account_move_line.subscription_id) AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        #"account_move_line.subscription_id IS NOT NULL"
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    return 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']


def compute_mrr(start_date, end_date, filters):
    fields = ['SUM(account_move_line.subscription_mrr)']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')"
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    return 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']


def compute_logo_churn(start_date, end_date, filters):

    fields = ['COUNT(DISTINCT account_move_line.subscription_id) AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_id IS NOT NULL"
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    active_customers_1_month_ago = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    fields = ['COUNT(DISTINCT account_move_line.subscription_id) AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_move_line ail
                    WHERE ail.subscription_id = account_move_line.subscription_id
                    AND (date %(date)s BETWEEN ail.subscription_start_date AND ail.subscription_end_date)
                )
        """,
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    resigned_customers = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    return 0 if not active_customers_1_month_ago else 100*resigned_customers/float(active_customers_1_month_ago)


def compute_revenue_churn(start_date, end_date, filters):

    fields = ['SUM(account_move_line.subscription_mrr) AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_move_line ail
                    WHERE ail.subscription_id = account_move_line.subscription_id
                    AND (date %(date)s BETWEEN ail.subscription_start_date AND ail.subscription_end_date)
                )
        """
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    churned_mrr = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']
    previous_month_mrr = compute_mrr(start_date, (end_date - relativedelta(months=+1)), filters)
    return 0 if previous_month_mrr == 0 else 100*churned_mrr/float(previous_month_mrr)


def compute_mrr_growth_values(start_date, end_date, filters):
    new_mrr = 0
    expansion_mrr = 0
    down_mrr = 0
    churned_mrr = 0
    net_new_mrr = 0

    # 1. NEW
    fields = ['SUM(account_move_line.subscription_mrr) AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_move_line ail
                    WHERE ail.subscription_id = account_move_line.subscription_id
                    AND (date %(date)s - interval '1 months' BETWEEN ail.subscription_start_date AND ail.subscription_end_date)
                )
        """
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    new_mrr = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    # 2. DOWN & EXPANSION
    fields = ['account_move_line.subscription_id', 'SUM(account_move_line.subscription_mrr) AS sum']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
    ]
    groupby = "account_move_line.subscription_id"

    subquery_1 = _build_sql_query(fields, tables, [
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_start_date BETWEEN date %(date)s - interval '1 months' + interval '1 days' and date %(date)s"
    ], {'date': end_date}, filters, groupby=groupby)

    subquery_2 = _build_sql_query(fields, tables, [
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_end_date BETWEEN date %(date)s - interval '1 months' + interval '1 days' and date %(date)s"
    ], {'date': end_date}, filters, groupby=groupby)

    computed_query = """
        SELECT old_line.subscription_id, old_line.sum AS old_sum, new_line.sum AS new_sum, (new_line.sum - old_line.sum) AS diff
        FROM ( """ + subquery_1[0] + """ ) AS new_line, ( """ + subquery_2[0] + """ ) AS old_line
        WHERE
            new_line.subscription_id IS NOT NULL AND
            old_line.subscription_id = new_line.subscription_id
    """
    request.cr.execute(computed_query, subquery_1[1])

    sql_results = request.cr.dictfetchall()
    for account in sql_results:
        if account['diff'] > 0:
            expansion_mrr += account['diff']
        else:
            down_mrr -= account['diff']

    # 3. CHURNED
    fields = ['SUM(account_move_line.subscription_mrr)']
    tables = ['account_move_line', 'account_move']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_move_line.subscription_start_date AND account_move_line.subscription_end_date",
        "account_move.id = account_move_line.move_id",
        "account_move.type IN ('out_invoice', 'out_refund')",
        "account_move.state NOT IN ('draft', 'cancel')",
        "account_move_line.subscription_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_move_line ail
                    WHERE ail.subscription_id = account_move_line.subscription_id
                    AND (date %(date)s BETWEEN ail.subscription_start_date AND ail.subscription_end_date)
                )
        """,
    ]

    sql_results = _execute_sql_query(fields, tables, conditions, {
        'date': end_date,
    }, filters)

    churned_mrr = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    net_new_mrr = new_mrr - churned_mrr + expansion_mrr - down_mrr

    return {
        'new_mrr': new_mrr,
        'churned_mrr': -churned_mrr,
        'expansion_mrr': expansion_mrr,
        'down_mrr': -down_mrr,
        'net_new_mrr': net_new_mrr,
    }


STAT_TYPES = {
    'mrr': {
        'name': _lt('Monthly Recurring Revenue'),
        'code': 'mrr',
        'dir': 'up',
        'prior': 1,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_mrr
    },
    'net_revenue': {
        'name': _lt('Net Revenue'),
        'code': 'net_revenue',
        'dir': 'up',
        'prior': 2,
        'type': 'sum',
        'add_symbol': 'currency',
        'compute': compute_net_revenue
    },
    'nrr': {
        'name': _lt('Non-Recurring Revenue'),
        'code': 'nrr',
        'dir': 'up',  # 'down' if fees ?
        'prior': 3,
        'type': 'sum',
        'add_symbol': 'currency',
        'compute': compute_nrr
    },
    'arpu': {
        'name': _lt('Revenue per Subscription'),
        'code': 'arpu',
        'dir': 'up',
        'prior': 4,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_arpu
    },
    'arr': {
        'name': _lt('Annual Run-Rate'),
        'code': 'arr',
        'dir': 'up',
        'prior': 5,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_arr
    },
    'ltv': {
        'name': _lt('Lifetime Value'),
        'code': 'ltv',
        'dir': 'up',
        'prior': 6,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_ltv
    },
    'logo_churn': {
        'name': _lt('Logo Churn'),
        'code': 'logo_churn',
        'dir': 'down',
        'prior': 7,
        'type': 'last',
        'add_symbol': '%',
        'compute': compute_logo_churn
    },
    'revenue_churn': {
        'name': _lt('Revenue Churn'),
        'code': 'revenue_churn',
        'dir': 'down',
        'prior': 8,
        'type': 'last',
        'add_symbol': '%',
        'compute': compute_revenue_churn
    },
    'nb_contracts': {
        'name': _lt('Subscriptions'),
        'code': 'nb_contracts',
        'dir': 'up',
        'prior': 9,
        'type': 'last',
        'add_symbol': '',
        'compute': compute_nb_contracts
    },
}

FORECAST_STAT_TYPES = {
    'mrr_forecast': {
        'name': _lt('Forecasted Annual MRR Growth'),
        'code': 'mrr_forecast',
        'prior': 1,
        'add_symbol': 'currency',
    },
    'contracts_forecast': {
        'name': _lt('Forecasted Annual Subscriptions Growth'),
        'code': 'contracts_forecast',
        'prior': 2,
        'add_symbol': '',
    },
}
