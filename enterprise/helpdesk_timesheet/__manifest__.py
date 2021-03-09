# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk Timesheet',
    'category': 'Operations/Helpdesk',
    'summary': 'Project, Tasks, Timesheet',
    'depends': ['helpdesk', 'hr_timesheet', 'project_enterprise'],
    'description': """
        - Allow to set project for Helpdesk team
        - Track timesheet for a task from a ticket
    """,
    'data': [
        'security/ir.model.access.csv',
        'security/helpdesk_timesheet_security.xml',
        'views/helpdesk_views.xml',
        'views/project_views.xml',
        'data/helpdesk_timesheet_data.xml',
    ],
    'license': 'OEEL-1',
}
