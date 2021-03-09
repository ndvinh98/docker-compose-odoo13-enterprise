# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Planning",
    'summary': """Plan your resources on project tasks""",
    'description': """
    Schedule your teams across projects and estimate deadlines more accurately.
    """,
    'category': 'Operations/Project',
    'version': '1.0',
    'depends': ['project', 'planning'],
    'data': [
        'views/planning_views.xml',
        'views/project_forecast_views.xml',
        'views/project_views.xml',
        'data/project_forecast_data.xml',
    ],
    'application': False,
    'license': 'OEEL-1',
}
