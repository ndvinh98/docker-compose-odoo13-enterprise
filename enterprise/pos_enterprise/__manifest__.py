# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale enterprise',
    'category': 'Sales/Point Of Sale',
    'summary': 'Advanced features for PoS',
    'description': """
Advanced features for the PoS like better views 
for IoT Box config.   
""",
    'data': [
        'views/pos_config_view.xml',
    ],
    'depends': ['web_enterprise', 'point_of_sale'],
    'auto_install': True,
    'license': 'OEEL-1',
}
