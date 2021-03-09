# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Luxembourg Standard Audit File for Tax',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'description': """
    Under Construction
    """,
    'depends': [
        'l10n_lu_reports', 'account_saft',
    ],
    'data': [
        'data/ir_cron_data.xml',
        'views/saft_report_templates.xml'
    ],
    'license': 'OEEL-1',
    'auto_install': True,
}
