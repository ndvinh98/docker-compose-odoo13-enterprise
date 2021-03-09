# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sign',
    'version': '1.0',
    'category': 'Sales/Sign',
    'summary': "Send documents to sign online and handle filled copies",
    'description': """
Sign and complete your documents easily. Customize your documents with text and signature fields and send them to your recipients.\n
Let your customers follow the signature process easily.
    """,
    'website': 'https://www.odoo.com/page/sign',
    'depends': ['mail', 'attachment_indexation', 'portal', 'sms'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',

        'views/sign_template_views_mobile.xml',

        'wizard/sign_send_request_views.xml',
        'wizard/sign_template_share_views.xml',
        'wizard/sign_request_send_copy_views.xml',

        'views/sign_request_templates.xml',
        'views/sign_template_templates.xml',

        'views/sign_request_views.xml',
        'views/sign_template_views.xml',
        'views/sign_log_views.xml',

        'views/res_users_views.xml',
        'views/res_partner_views.xml',

        'report/sign_log_reports.xml',

        'data/sign_data.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'demo': [
        'data/sign_demo.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'OEEL-1',
}
