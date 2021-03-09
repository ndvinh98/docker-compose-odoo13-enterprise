# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Lead to Tickets',
    'summary': 'Create Tickets from Leads',
    'sequence': '19',
    'category': 'Operations/Helpdesk',
    'complexity': 'easy',
    'description': """
Lead to Tickets
===============

Link module to map leads to tickets
        """,
    'data': [
        'security/ir.model.access.csv',
        'wizard/crm_lead_convert2ticket_views.xml',
        'views/crm_lead_views.xml'
    ],
    'depends': ['crm', 'helpdesk'],
}
