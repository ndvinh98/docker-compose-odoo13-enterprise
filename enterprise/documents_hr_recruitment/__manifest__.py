# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Recruitment',
    'version': '1.0',
    'category': 'Operations/Documents',
    'summary': 'Recruitment resumés and letters from documents',
    'description': """
Add the ability to manage resumés and letters from the Documents app.
""",
    'website': ' ',
    'depends': ['documents_hr', 'hr_recruitment'],
    'data': ['data/documents_hr_recruitment_data.xml', 'views/res_config_settings_views.xml'],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
