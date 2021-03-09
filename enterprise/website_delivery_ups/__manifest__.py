# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'UPS: Bill My Account',
    'category': 'Operations/Inventory/Delivery',
    'summary': 'Bill to your UPS account number',
    'description': """
This module allows ecommerce users to enter their UPS account number and delivery fees will be charged on that account number.
    """,
    'depends': ['delivery_ups', 'website_sale_delivery'],
    'data': [
        'data/payment_acquirer_data.xml',
        'views/delivery_ups_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
