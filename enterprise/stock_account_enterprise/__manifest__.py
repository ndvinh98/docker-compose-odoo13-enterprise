# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Stock account enterprise",
    'version': "1.0",
    'category': 'Operations/Inventory',
    'summary': "Advanced features for stock_account",
    'description': """
Contains the enterprise views for Stock account
    """,
    'depends': ['stock_account', 'stock_enterprise', 'web_dashboard'],
    'data': [
        'report/stock_report_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': ['stock_account'],
    'license': 'OEEL-1',
}
