# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Event Barcode in Mobile',
    'category': 'Mobile',
    'summary': 'Event Barcode scan in Mobile',
    'version': '1.0',
    'description': """ """,
    'depends': ['event_barcode', 'web_mobile'],
    'qweb': ['static/src/xml/event_barcode_mobile.xml'],
    'data': ['views/event_barcode_mobile_template.xml'],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
