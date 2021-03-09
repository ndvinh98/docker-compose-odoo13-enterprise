# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Sale enterprise",
    'version': "1.0",
    'category': "Sales/Sales",
    'summary': "Advanced Features for Sale Management",
    'description': """
Contains advanced features for sale management
    """,
    'depends': ['sale', 'web_dashboard'],
    'data': [
        'report/sale_report_views.xml',
        'views/sale_enterprise_templates.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': ['sale'],
    'license': 'OEEL-1',
}
