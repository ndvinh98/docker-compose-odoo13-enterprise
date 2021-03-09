# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Quality checks with IoT',
    'category': 'Tools',
    'summary': 'Control the quality of your products with IoT devices',
    'depends': ['quality_control', 'iot'],
    'data': [
        'views/quality_views.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
