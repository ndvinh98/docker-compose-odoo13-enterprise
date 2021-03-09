# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Purchase enterprise",
    'version': "1.0",
    'category': "Operations/Purchase",
    'summary': "Advanced Features for Purchase Management",
    'description': """
Contains advanced features for purchase management
    """,
    'depends': ['purchase', 'web_dashboard'],
    'data': [
        'report/purchase_report_views.xml',
    ],
    'demo': [
        'data/purchase_order_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': ['purchase'],
}
