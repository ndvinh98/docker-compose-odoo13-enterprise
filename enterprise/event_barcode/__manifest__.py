# -*- coding: utf-8 -*-

{
    'name': "Event Barcode Scanning",
    'summary': "Add barcode scanning feature to event management.",
    'description': """
This module adds support for barcodes scanning to the Event management system.
A barcode is generated for each attendee and printed on the badge. When scanned,
the registration is confirmed.
    """,
    'category': 'Tools',
    'depends': ['barcodes', 'event'],
    'data': [
        'views/event_barcode_template.xml',
        'views/event_barcode.xml',
        'views/event_report_template_badge.xml',
        'views/res_config_settings_views.xml',
    ],
    'qweb': [
        "static/src/xml/event_barcode.xml",
    ],
    'license': 'OEEL-1',
}
