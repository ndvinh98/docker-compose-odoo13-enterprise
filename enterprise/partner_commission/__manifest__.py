# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Resellers Commissions For Subscription',
    'category': 'Website',
    'summary': 'Configure resellers commissions on subscription sale',
    'version': '1.0',
    'description': """
This module allows to configure commissions for resellers.
    """,
    'depends': [
        'purchase',
        'sale_subscription',
        'website_crm_partner_assign',
    ],
    'data': [
        'data/data.xml',
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/commission_views.xml',
        'views/purchase_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/sale_subscription_views.xml',
    ],
}
