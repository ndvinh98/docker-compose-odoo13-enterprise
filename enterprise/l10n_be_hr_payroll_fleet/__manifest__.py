# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Payroll - Fleet',
    'category': 'Human Resources',
    'depends': ['l10n_be_hr_payroll', 'fleet'],
    'description': """
    """,
    'data': [
        'security/ir.model.access.csv',
        'data/hr_rule_parameter_data.xml',
        'data/cp200_employee_salary_data.xml',
        'views/fleet_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_dmfa_templates.xml',
        'views/report_payslip_templates.xml',
        'views/hr_payslip_views.xml',
        'security/security.xml',
    ],
    'auto_install': True,
}
