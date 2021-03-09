# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Account Invoice Extract',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Extract data from invoice scans to fill them automatically',
    'depends': ['account', 'iap', 'mail_enterprise'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_invoice_extract_data.xml',
        'data/config_parameter_endpoint.xml',
        'data/extraction_status.xml',
        'data/res_config_settings_views.xml',
        'data/update_status_cron.xml',
    ],
    'auto_install': True,
    'qweb': [
        'static/src/xml/invoice_extract_box.xml',
        'static/src/xml/invoice_extract_button.xml',
    ],
    'license': 'OEEL-1',
}
