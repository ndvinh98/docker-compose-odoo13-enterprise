# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Belgian Registered Cash Register Employee module",
    'category': "Hidden",
    'summary': 'Link module between Pos Blackbox Be and Pos HR',

    'description': """
This module allows Employees (and not users) to log in to the Point of Sale application using the fiscal data module
    """,

    'depends': ['pos_blackbox_be', 'pos_hr'],

    'data': [
        'views/pos_hr_l10n_be_assets.xml',
        'views/hr_employee_view.xml',
        'data/pos_hr_l10n_be_data.xml',
    ],
    'installable': False,
    'auto_install': False,
    'qweb': [],
}
