# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Electronic invoicing for Colombia with Carvajal',
    'version': '0.1',
    'category': 'Accounting/Accounting',
    'summary': 'Colombian Localization for EDI documents',
    'author': 'Odoo Sa',
    'depends': ['account', 'l10n_co'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_invoice.xml',
        'data/l10n_co_edi.type_code.csv',
        'data/l10n_co_edi.tax.type.csv',
        'views/account_invoice_views.xml',
        'views/account_tax_views.xml',
        'views/account_journal_views.xml',
        'views/product_template_views.xml',
        'views/product_uom_views.xml',
        'views/type_code_views.xml',
        'views/res_partner_views.xml',
        'views/tax_type_views.xml',
        'views/res_config_settings_views.xml',
        'views/electronic_invoice.xml',
    ],
    'installable': True,
    'license': 'OEEL-1',
}
