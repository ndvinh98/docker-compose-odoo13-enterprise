# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) David Arnold (XOE Solutions).
# Author        David Arnold (XOE Solutions), dar@xoe.solutions
# Co-Authors    Juan Pablo Aries (devCO), jpa@devco.co
#               Hector Ivan Valencia Muñoz (TIX SAS)
#               Nhomar Hernandez (Vauxoo)
#               Humberto Ochoa (Vauxoo)

{
    'name': 'Colombian - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for Colombia
================================
    """,
    'author': ['David Arnold (XOE Solutions)'],
    'category': 'Accounting/Accounting',
    'depends': ['l10n_co', 'account_reports'],
    'data': [
        'data/l10n_co_reports.xml',
        'wizard/retention_report_views.xml',
        'report/certification_report_templates.xml',
    ],
    'demo': [],
    'auto_install': True,
    'installable': True,
    'website': 'https://xoe.solutions',
    'license': 'OEEL-1',
}
