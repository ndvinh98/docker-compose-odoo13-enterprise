# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Github Integration with Discuss',
    'category': 'Discuss',
    'depends': ['mail'],
    'description': """
Integrate Github to Odoo Discuss.
======================================

This Module integrates all post commits, pull requests and activity of github issue to channels in Odoo.
    """,
    'data': [
        'data/mail_channel_github_data.xml',
        'views/mail_channel_views.xml',
        'views/mail_channel_github_views.xml',
        'views/res_users_views.xml',
        'security/ir.model.access.csv'
    ],
    'license': 'OEEL-1',
}
