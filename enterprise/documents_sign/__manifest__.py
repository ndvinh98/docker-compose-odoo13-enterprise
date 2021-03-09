# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Signatures',
    'version': '1.0',
    'category': 'Operations/Documents',
    'summary': 'Signature templates from Documents',
    'description': """
Add the ability to create signatures from the document module.
The first element of the selection (in DRM) will be used as the signature attachment.
""",
    'website': ' ',
    'depends': ['documents', 'sign'],

    'data': [
        'data/data.xml',
        'views/sign_templates.xml',
    ],

    'demo': [
        'demo/demo.xml',
    ],

    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
