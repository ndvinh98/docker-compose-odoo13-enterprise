# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Contract - Signature',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Manage your documents to sign in contracts',
    'description': "",
    'website': ' ',
    'depends': ['hr_contract', 'sign'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/hr_contract_sign_document_wizard_view.xml',
        'views/hr_contract_view.xml',
        'views/hr_employee_view.xml',
        'views/res_users_view.xml',
        'views/sign_request_views.xml',
        'data/hr_contract_data.xml',
    ],
    'installable': True,
    'auto_install': True,
}
