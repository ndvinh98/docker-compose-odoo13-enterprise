# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk After Sales',
    'category': 'Operations/Helpdesk',
    'summary': 'Project, Tasks, After Sales',
    'depends': ['helpdesk', 'sale_management'],
    'auto_install': True,
    'description': """
Manage the after sale of the products from helpdesk tickets.
    """,
    'data': [
        'views/helpdesk_views.xml',
    ],
}
