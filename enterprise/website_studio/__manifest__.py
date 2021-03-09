# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Website Studio",
    'summary': "Display Website Elements in Studio",
    'description': """
Studio - Customize Odoo
=======================

This addon allows the user to display all the website forms linked to a certain
model. Furthermore, you can create a new website form or edit an existing one.

""",
    'category': 'Hidden',
    'version': '1.0',
    'depends': [
        'web_studio',
        'website_form',
    ],
    'data': [
        'views/assets.xml',
        'views/templates.xml',
        'views/actions.xml',
    ],
    'qweb': [
        'static/src/xml/*.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
