# -*- coding: utf-8 -*-
{
    'name': "Documents",

    'summary': "Document management",

    'description': """
        App to upload and manage your documents.
    """,

    'author': "Odoo",
    'category': 'Operations/Documents',
    'version': '1.0',
    'application': True,
    'website': 'https://www.odoo.com/page/documents',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'portal', 'web', 'attachment_indexation'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/documents_data.xml',
        'data/workflow_data.xml',
        'data/files_data.xml',
        'data/mail_templates.xml',
        'views/assets.xml',
        'views/documents_views.xml',
        'views/templates.xml',
        'views/activity_views.xml',
        'wizard/request_activity_views.xml',
    ],

    'qweb': [
        "static/src/xml/*.xml",
    ],

    'demo': [
        'demo/demo.xml',
    ],
    'license': 'OEEL-1',
}
