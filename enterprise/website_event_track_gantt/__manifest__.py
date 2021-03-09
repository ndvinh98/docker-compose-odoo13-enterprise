# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Advanced Events Gantt',
    'category': 'Marketing',
    'summary': 'Gantt View for Advanced Events',
    'version': '1.0',
    'description': "Gantt View for Advanced Events",
    'depends': ['website_event_track', 'web_gantt'],
    'auto_install': True,
    'data': [
        'views/event_track_views.xml',
    ],
    'license': 'OEEL-1',
}
