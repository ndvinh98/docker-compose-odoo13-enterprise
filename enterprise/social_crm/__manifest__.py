# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'CRM statistics on social',
    'category': 'Hidden',
    'version': '1.0',
    'summary': 'Add crm UTM info on social',
    'description': """UTM and posts on crm""",
    'depends': ['social', 'crm'],
    'data': [
        'views/social_post_views.xml',
    ],
    'auto_install': True,
}
