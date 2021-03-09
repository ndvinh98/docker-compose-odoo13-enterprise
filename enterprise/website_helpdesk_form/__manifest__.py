# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Online Ticket Submission',
    'category': 'Website/Website',
    'sequence': 58,
    'summary': 'Qualify helpdesk queries with a website form',
    'depends': [
        'website_form',
        'website_helpdesk',
    ],
    'description': """
Generate tickets in Helpdesk app from a form published on your website. This form can be customized thanks to the *Form Builder* module (available in Odoo Enterprise).
    """,
    'data': [
        'data/website_helpdesk.xml',
        'views/helpdesk_views.xml',
        'views/helpdesk_templates.xml'
    ],
    'license': 'OEEL-1',
}
