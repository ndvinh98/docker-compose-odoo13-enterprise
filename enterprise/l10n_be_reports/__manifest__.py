# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Accounting Reports',
    'version': '1.1',
    'category': 'Accounting/Accounting',
    'description': """
        Accounting reports for Belgium
    """,
    'depends': [
        'l10n_be', 'account_reports'
    ],
    'data': [
        'views/l10n_be_vat_statement_views.xml',
        'views/l10n_be_wizard_xml_export_options_views.xml',
        'data/account_financial_html_report_data.xml',
        'data/account_tag_data.xml',
    ],
    'installable': True,
    'auto_install': True,
    'website': 'https://www.odoo.com/page/accounting',
    'license': 'OEEL-1',
}
