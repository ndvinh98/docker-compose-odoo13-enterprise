# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Planning",
    'summary': """Manage your employees' schedule""",
    'description': """
    Schedule your teams and employees with shift.
    """,
    'category': 'Human Resources/Planning',
    'version': '1.0',
    'depends': ['hr', 'web_gantt'],
    'data': [
        'security/planning_security.xml',
        'security/ir.model.access.csv',
        'wizard/planning_send_views.xml',
        'views/assets.xml',
        'views/hr_views.xml',
        'report/planning_report_views.xml',
        'views/planning_template_views.xml',
        'views/planning_views.xml',
        'views/res_config_settings_views.xml',
        'views/planning_templates.xml',
        'data/planning_cron.xml',
        'data/mail_data.xml',
    ],
    'demo': [
        'data/planning_demo.xml',
    ],
    'application': True,
    'license': 'OEEL-1',
    'qweb': [
        'static/src/xml/planning_gantt.xml',
        'static/src/xml/field_colorpicker.xml',
    ]
}
