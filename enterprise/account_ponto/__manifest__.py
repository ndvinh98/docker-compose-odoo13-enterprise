# -*- coding: utf-8 -*-
{
    'name': "account_ponto",

    'summary': """
        Use myponto.com to retrieve bank statements""",

    'description': """
        This module connects to my myponto.com to retrieve bank statements.

        Currently, that service allows to connect to belgian banks only
        (BNP Paribas Fortis, KBC, CBC, KBC Brussels, Fintro, Hello Bank, ING Belgium, AXA Belgium)
        but aims to connect with all European banks later on
    """,

    'category': 'Accounting/Accounting',
    'version': '1.0',

    'depends': ['account_online_sync'],

    'data': [
        'views/ponto_views.xml',
    ],
    'qweb': [
        'views/ponto_template.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': True,
}
