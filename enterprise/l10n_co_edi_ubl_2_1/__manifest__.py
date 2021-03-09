# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Electronic invoicing for Colombia with Carvajal UBL 2.1',
    'version': '0.1',
    'category': 'Accounting',
    'summary': 'Colombian Localization for EDI documents UBL 2.1',
    'depends': ['l10n_co_edi', 'base_address_city', 'product_unspsc'],
    'data': [
        'data/l10n_co_edi.tax.type.csv',
        'data/account.tax.template.csv',
        'data/l10n_co_edi.payment.option.csv',
        'data/l10n_co_edi.type_code.csv',
        'data/res.city.csv',
        'data/res.country.state.csv',
        'data/res_country_data.xml',
        'data/res_partner_data.xml',
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_journal_views.xml',
        'views/electronic_invoice.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_country_state_views.xml',
        'views/res_partner_views.xml',
        'wizard/account_move_reversal_views.xml'
    ],
    'installable': True,
    'license': 'OEEL-1',
    'post_init_hook': '_setup_tax_type'
}
