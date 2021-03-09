# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk Account',
    'category': 'Operations/Helpdesk',
    'summary': 'Project, Tasks, Account',
    'depends': ['helpdesk_sale', 'account'],
    'auto_install': False,
    'description': """
Create Credit Notes from Helpdesk tickets
    """,
    'data': [
        'wizard/account_move_reversal_views.xml',
        'views/helpdesk_views.xml',
    ],
}
