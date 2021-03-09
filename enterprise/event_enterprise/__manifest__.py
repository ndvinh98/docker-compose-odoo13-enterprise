# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Events Organization Add-on",
    'summary': "Displays cohort analysis on attendees.",
    'description': """
This module helps for analyzing event registration pattern,
by enabling cohort view for registered attendees.
    """,
    'category': 'Marketing/Events',
    'depends': ['event', 'web_cohort'],
    'data': [
        'views/event_registration_views.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
