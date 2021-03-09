# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Denmark - Accounting Reports',
    'version': '1.0',
    'author': 'Odoo House ApS',
    'website': 'https://odoohouse.dk',
    'category': 'Localization',
    'description': """
Accounting reports for Denmark
=================================
    """,
    'depends': ['l10n_dk', 'account_reports'],
    'data': [
        'data/account_income_statement_html_report_data.xml',
        'data/account_balance_dk_html_report_data.xml'
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
