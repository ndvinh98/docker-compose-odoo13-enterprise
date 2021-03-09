# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Stock',
    'category': 'Hidden',
    'summary': 'Validate stock moves for product added on sales orders through Field Service Management App',
    'description': """
Validate stock moves for Field Service
======================================
""",
    'depends': ['industry_fsm', 'sale_stock'],
    'auto_install': True,
}
