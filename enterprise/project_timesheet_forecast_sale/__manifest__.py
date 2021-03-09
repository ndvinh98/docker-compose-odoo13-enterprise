# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Compare timesheets and forecast for your projects',
    'version': '1.0',
    'category': 'Operations/Project',
    'description': """
Compare timesheets and forecast for your projects.
==================================================

In your project plan, you can compare your timesheets and your forecast to better schedule your resources.
    """,
    'website': 'https://www.odoo.com/page/project-management',
    'depends': ['project_forecast', 'sale_timesheet'],
    'data': [
        'views/project_templates.xml'
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
