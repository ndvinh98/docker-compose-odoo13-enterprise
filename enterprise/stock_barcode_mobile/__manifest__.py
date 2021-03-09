# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Stock Barcode in Mobile',
    'category': 'Mobile',
    'summary': 'Stock Barcode scan in Mobile',
    'version': '1.0',
    'description': """ """,
    'depends': ['stock_barcode', 'web_mobile'],
    'qweb': ['static/src/xml/stock_mobile_barcode.xml'],
    'data': ['views/stock_barcode_template.xml'],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
