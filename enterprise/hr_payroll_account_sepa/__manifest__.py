# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "SEPA Payments for Payroll",
    'summary': "Pay your employees with SEPA payment.",
    'description': '',
    'category': 'Human Resources/Payroll',
    'version': '1.0',
    'depends': ['hr_payroll_account', 'account_sepa'],
    'data': [
        'views/hr_payroll_account_sepa_views.xml',
        'wizard/hr_payroll_account_sepa_wizard_views.xml',
    ],
}
