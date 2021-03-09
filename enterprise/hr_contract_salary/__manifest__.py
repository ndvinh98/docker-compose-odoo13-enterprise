# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'HR Contract Salary (Belgium)',
    'category': 'Human Resources',
    'summary': 'Salary Package Configurator',
    'depends': [
        'hr_contract_sign',
        'website',
        'hr_recruitment',
        'l10n_be_hr_payroll_fleet',
        'sign',
    ],
    'description': """
    """,
    'data': [
        'wizard/generate_simulation_link_views.xml',
        'views/hr_applicant_views.xml',
        'views/hr_contract_salary_templates.xml',
        'views/hr_contract_views.xml',
        'views/hr_job_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'data/hr_contract_salary_data.xml',
    ],
    'demo': [
        'data/hr_contract_salary_demo.xml',
    ],
    'license': 'OEEL-1',
}
