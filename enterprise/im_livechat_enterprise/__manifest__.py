# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Live chat enterprise",
    'version': "1.0",
    'category': 'Website/Website',
    'summary': "Advanced features for Live Chat",
    'description': """
Contains advanced features for Live Chat such as new views
    """,
    'depends': ['im_livechat', 'web_dashboard'],
    'data': [
        'views/im_livechat_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': ['im_livechat'],
}
