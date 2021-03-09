# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - HR',
    'version': '1.0',
    'category': 'Operations/Documents',
    'summary': 'Access documents from the employee profile',
    'description': """
Easily access your documents from your employee profile.
""",
    'website': ' ',
    'depends': ['documents', 'hr'],
    'data': [
        'data/documents_hr_data.xml',
        'views/res_config_settings_views.xml',
        'views/hr_employee_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
