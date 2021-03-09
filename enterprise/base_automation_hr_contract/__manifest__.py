# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Automated Action based on Employee Contracts',
    'version': '1.0',
    'category': 'Human Resources',
    'description': """
Bridge to add contract calendar on automated actions
====================================================
    """,
    'depends': ['base_automation', 'hr_contract'],
    'data': [
        'views/base_automation_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
