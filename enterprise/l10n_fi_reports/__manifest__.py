# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Finland - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for Finland
================================

    """,
    'category': 'Accounting',
    'depends': ['l10n_fi', 'account_reports'],
    'data': [
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
    ],
    'demo': [],
    'auto_install': True,
    'installable': True,
    'license': 'OEEL-1',
}
