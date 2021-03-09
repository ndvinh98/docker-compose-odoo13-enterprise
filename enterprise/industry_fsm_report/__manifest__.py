# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Reports',
    'category': 'Hidden',
    'summary': 'Create Reports for Field service workers',
    'description': """
Create Reports for Field Service
================================

""",
    'depends': ['project', 'web_studio', 'industry_fsm'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/product_template_views.xml',
        'views/assets.xml',
        'views/project_portal_templates.xml',
        'report/worksheet_custom_reports.xml',
        'report/worksheet_custom_report_templates.xml',
        'data/fsm_report_data.xml',
    ],
    'demo': ['data/fsm_report_demo.xml'],
    'post_init_hook': '_configure_fsm_project',
}
