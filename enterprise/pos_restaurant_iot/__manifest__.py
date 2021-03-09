# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': '',
    'version': '1.0',
    'category': 'Sales/Point Of Sale',
    'sequence': 6,
    'summary': 'Link your PoS configuration with an IoT Box for the restaurant',
    'description': """
It links the module iot with the pos restaurant, so you don't have to call the  
""",
    'data': ['views/restaurant_printer_views.xml',],
    'depends': ['pos_restaurant', 'iot'],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
