# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk: Knowledge Base',
    'category': 'Operations/Helpdesk',
    'sequence': 58,
    'summary': 'Knowledge base for helpdesk based on Odoo Forum',
    'depends': [
        'website_forum',
        'website_helpdesk'
    ],
    'description': """
Website Forum integration for the helpdesk module
=================================================

    Allow your teams to have a related forum to answer customer questions.
    Transform tickets into questions on the forum with a single click.

    """,
    'data': [
        'views/helpdesk_templates.xml',
        'views/helpdesk_views.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
