# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Cloud Notification Client (OCN)',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Allow push notification to devices',
    'description': """
Odoo Cloud Notifications (OCN)
===============================

This module enables push notifications to registered devices for direct messages,
chatter messages and channel.
    """,
    'depends': [
        'iap',
        'mail',
        'web_mobile',
    ],
    'data': [
        'views/ocn_assets.xml'
    ],
    'installable': True,
    'license': 'OEEL-1',
}
