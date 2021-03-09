# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Approvals',
    'version': '1.0',
    'category': 'Human Resources/Approvals',
    'summary': 'Create and validate approvals requests',
    'description': """
This module manages approvals workflow
======================================

This module manages approval requests like business trips,
out of office, overtime, borrow items, general approvals,
procurements, contract approval, etc.

According to the approval type configuration, a request
creates next activities for the related approvers.
    """,
    'depends': ['mail', 'hr'],
    'data': [
        'security/approval_security.xml',
        'security/ir.model.access.csv',

        'data/approval_category_data.xml',
        'data/mail_activity_data.xml',

        'views/approval_template.xml',
        'views/approval_category_views.xml',
        'views/approval_request_views.xml',
        'views/res_users_views.xml',
    ],
    'demo':[
        'data/approval_demo.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
