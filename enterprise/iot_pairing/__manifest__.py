# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'IoT Pairing',
    'summary': 'IoT Box pairing through odoo.com.',
    'description': """
This module enables the pairing of the IoT Box with Odoo through odoo.com.
""",
    'depends': ['iot'],
    'data': [
        'wizard/iot_wizard.xml',
    ],
    'installable': True,
    'auto_install': True,
}
