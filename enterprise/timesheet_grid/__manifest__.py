# -*- coding: utf-8 -*-

{
    'name': "Timesheets",
    'summary': "Timesheet Validation and Grid View",
    'description': """
* Timesheet submission and validation
* Activate grid view for timesheets
    """,
    'version': '1.0',
    'depends': ['web_grid', 'hr_timesheet'],
    'category': 'Operations/Timesheets',
    'data': [
        'data/mail_data.xml',
        'security/timesheet_security.xml',
        'views/hr_timesheet_views.xml',
        'views/res_config_settings_views.xml',
        'views/timesheet_templates.xml',
        'wizard/timesheet_validation_views.xml',
    ],
    'website': ' https://www.odoo.com/page/timesheet-mobile-app',
    'auto_install': True,
    'application': True,
    'license': 'OEEL-1',
    'pre_init_hook': 'pre_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
