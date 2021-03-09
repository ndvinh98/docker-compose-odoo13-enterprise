# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mobile',
    'category': 'Mobile',
    'summary': 'Odoo Mobile Core module',
    'version': '1.0',
    'description': """
        This module provides the core of the Odoo Mobile App.
        """,
    'depends': [
        'base_setup',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'data': [
        'views/mobile_template.xml',
        'views/views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
