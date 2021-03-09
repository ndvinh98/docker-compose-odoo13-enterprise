# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Time off Gantt - Calendar",
    'summary': """""",
    'description': """""",
    'category': 'Human Resources',
    'version': '1.0',
    'depends': ['hr_holidays_calendar', 'web_gantt'],
    'auto_install': True,
    'data': [
        'report/hr_leave_report_calendar_views.xml',
    ],
    'license': 'OEEL-1',
}
