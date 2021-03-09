# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Chile - Accounting Reports',
    'version': '1.1',
    'category': 'Accounting',
    'author': 'CubicERP, Blanco Martin y Asociados',
    'description': """
        Accounting reports for Chile
    """,
    'depends': [
        'l10n_cl', 'account_reports',
    ],
    'data': [
        'views/eightcolumns_report_view.xml',
        'views/res_config_settings_view.xml',
        'wizard/f29_report_wizard.xml',
        'data/f29_report_data.xml',
    ],
    'installable': True,
    'auto_install': True,
    'website': 'http://cubicERP.com',
    'license': 'OEEL-1',
}
