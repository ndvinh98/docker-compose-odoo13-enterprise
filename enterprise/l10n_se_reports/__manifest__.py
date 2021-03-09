# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sweden - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'author': "XCLUDE",
    'website': "https://www.xclude.se",
    'description': """
        Accounting reports for Sweden
    """,
    'depends': [
        'l10n_se', 'account_reports'
    ],
    'data': [
        'views/report_export_template.xml'
    ],
    'installable': True,
    'auto_install': True,
    'website': 'https://www.odoo.com/page/accounting',
    'license': 'OEEL-1',
}
