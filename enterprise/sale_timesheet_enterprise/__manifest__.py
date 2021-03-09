# -*- coding: utf-8 -*-
{
    'name': "Sales Timesheet: Grid Support",

    'summary': "Configure timesheet invoicing",

    'description': """
        When invoicing timesheets, allows invoicing either all timesheets
        linked to an SO, or only the validated timesheets
    """,

    'category': 'Hidden',
    'version': '0.1',

    'depends': ['sale_timesheet', 'timesheet_grid'],
    'data': [
        'views/assets.xml',
        'views/res_config_settings_views.xml',
        'views/project_task_views.xml',
        'wizard/project_task_create_timesheet_views.xml',
        'wizard/project_task_create_sale_order_views.xml',
        'data/sale_timesheet_enterprise_data.xml',
    ],

    'auto_install': True,
    'license': 'OEEL-1',
}
