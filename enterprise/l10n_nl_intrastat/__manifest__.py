# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Netherlands Intrastat Declaration',
    'category': 'Localization',
    'description': """
Generates Netherlands Intrastat report for declaration based on invoices.
    """,
    'depends': ['l10n_nl', 'account_intrastat'],
    'data': [
        'views/res_company_view.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
