# -*- coding: utf-8 -*-
{
    'name': "Yodlee",
    'summary': "Yodlee Finance",
    'category': 'Accounting/Accounting',
    'version': '2.0',
    'depends': ['account_online_sync'],
    'description': '''
Sync your bank feeds with Yodlee
================================

Yodlee interface.
''',
    'data': [
        'views/yodlee_views.xml',
    ],
    'qweb': [
        'views/yodlee_templates.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': True,
}
