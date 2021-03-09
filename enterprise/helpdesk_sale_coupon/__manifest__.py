# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk Sale Coupon',
    'category': 'Operations/Helpdesk',
    'summary': 'Project, Tasks, Sale Coupon',
    'depends': ['helpdesk_sale', 'sale_coupon'],
    'auto_install': False,
    'description': """
Generate Coupons from Helpdesks tickets
    """,
    'data': [
        'wizard/helpdesk_sale_coupon_generate_views.xml',
        'views/helpdesk_views.xml',
    ],
}
