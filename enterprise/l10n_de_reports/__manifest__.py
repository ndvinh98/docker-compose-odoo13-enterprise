# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Germany - Accounting Reports',
    'version': '1.1',
    'category': 'Accounting/Accounting',
    'description': """
        Accounting reports for Germany
        Contains Balance sheet, Profit and Loss, VAT and Partner VAT reports
        Also adds DATEV export options to general ledger
    """,
    'depends': [
        'l10n_de', 'account_reports'
    ],
    'data': [
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
        'data/ir_config_param.xml',
        'views/l10n_de_report_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
