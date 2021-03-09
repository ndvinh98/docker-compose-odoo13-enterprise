# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Projects',
    'version': '1.0',
    'category': 'Operations/Documents',
    'summary': 'Project from documents',
    'description': """
Add the ability to create invoices from the document module.
""",
    'website': ' ',
    'depends': ['documents', 'project'],
    'data': ['data/data.xml', 'views/documents_views.xml'],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
