# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "CRM enterprise",
    'version': "1.0",
    'category': "Sales/CRM",
    'summary': "Advanced features for CRM",
    'description': """
Contains advanced features for CRM such as new views
    """,
    'depends': ['crm', 'web_dashboard', 'web_cohort', 'web_map'],
    'data': [
        'views/crm_lead_views.xml',
        'report/crm_activity_report_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': ['crm'],
    'license': 'OEEL-1',
}
