# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "United States Postal Service (USPS) Shipping",
    'description': "Send your shippings through USPS and track them online",
    'category': 'Operations/Inventory/Delivery',
    'version': '1.0',
    'application': True,
    'depends': ['delivery', 'mail'],
    'data': [
        'data/delivery_usps_data.xml',
        'views/delivery_usps_view.xml',
        'views/delivery_usps_template.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'OEEL-1',
    'uninstall_hook': 'uninstall_hook',
}
