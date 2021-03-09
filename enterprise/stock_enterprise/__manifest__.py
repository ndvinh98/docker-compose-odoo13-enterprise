# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Stock enterprise",
    'version': "1.0",
    'category': 'Operations/Inventory',
    'summary': "Advanced features for Stock",
    'description': """
Contains the enterprise views for Stock management
    """,
    'depends': ['stock', 'web_dashboard', 'web_cohort', 'web_map', 'web_grid'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_move_views.xml',
        'views/stock_picking_map_views.xml',
        'views/stock_enterprise_templates.xml',
        'report/stock_report_views.xml',
        'report/report_stock_quantity.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': ['stock'],
    'license': 'OEEL-1',
}
