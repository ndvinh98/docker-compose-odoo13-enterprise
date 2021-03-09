# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Website Helpdesk',
    'category': 'Hidden',
    'sequence': 57,
    'summary': 'Bridge module for helpdesk modules using the website.',
    'description': 'Bridge module for helpdesk modules using the website.',
    'depends': [
        'helpdesk',
        'website',
    ],
    'data': [
        'data/helpdesk_data.xml',
        'views/assets.xml',
        'views/helpdesk_views.xml',
        'views/helpdesk_templates.xml',
    ],
    'license': 'OEEL-1',
}
