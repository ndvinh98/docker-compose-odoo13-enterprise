# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk',
    'version': '1.2',
    'category': 'Operations/Helpdesk',
    'sequence': 57,
    'summary': 'Track help tickets',
    'website': 'https://www.odoo.com/page/helpdesk',
    'depends': [
        'base_setup',
        'mail',
        'utm',
        'rating',
        'web_tour',
        'resource',
        'portal',
        'digest',
    ],
    'description': """
Helpdesk - Ticket Management App
================================

Features:

    - Process tickets through different stages to solve them.
    - Add priorities, types, descriptions and tags to define your tickets.
    - Use the chatter to communicate additional information and ping co-workers on tickets.
    - Enjoy the use of an adapted dashboard, and an easy-to-use kanban view to handle your tickets.
    - Make an in-depth analysis of your tickets through the pivot view in the reports menu.
    - Create a team and define its members, use an automatic assignation method if you wish.
    - Use a mail alias to automatically create tickets and communicate with your customers.
    - Add Service Level Agreement deadlines automatically to your tickets.
    - Get customer feedback by using ratings.
    - Install additional features easily using your team form view.

    """,
    'data': [
        'security/helpdesk_security.xml',
        'security/ir.model.access.csv',
        'data/digest_data.xml',
        'data/mail_data.xml',
        'data/helpdesk_data.xml',
        'views/helpdesk_views.xml',
        'views/helpdesk_team_views.xml',
        'views/assets.xml',
        'views/digest_views.xml',
        'views/helpdesk_portal_templates.xml',
        'views/res_partner_views.xml',
        'views/mail_activity_views.xml',
        'report/helpdesk_sla_report_analysis_views.xml',
    ],
    'qweb': [
        "static/src/xml/helpdesk_team_templates.xml",
    ],
    'demo': ['data/helpdesk_demo.xml'],
    'application': True,
    'license': 'OEEL-1',
}
