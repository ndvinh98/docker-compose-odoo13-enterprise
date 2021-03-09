# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Social Twitter',
    'category': 'Social',
    'summary': 'Manage your Twitter accounts and schedule tweets',
    'version': '1.0',
    'description': """Manage your Twitter accounts and schedule tweets""",
    'depends': ['social', 'iap'],
    'data': [
        'security/ir.model.access.csv',
        'data/social_media_data.xml',
        'views/assets.xml',
        'views/social_post_views.xml',
        'views/social_stream_views.xml',
        'views/social_stream_post_views.xml',
        'views/social_twitter_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'qweb': [
        "static/src/xml/social_twitter_templates.xml",
    ],
    'auto_install': True,
}
