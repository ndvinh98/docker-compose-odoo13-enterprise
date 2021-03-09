# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Social Facebook',
    'category': 'Social',
    'summary': 'Manage your Facebook pages and schedule posts',
    'version': '1.0',
    'description': """Manage your Facebook pages and schedule posts""",
    'depends': ['social'],
    'data': [
        'data/social_media_data.xml',
        'views/assets.xml',
        'views/social_facebook_templates.xml',
        'views/social_post_views.xml',
        'views/social_stream_post_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'qweb': [
        "static/src/xml/social_facebook_templates.xml",
    ],
    'auto_install': True,
}
