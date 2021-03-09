# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Subscriptions',
    'version': '1.1',
    'category': 'Sales/Subscription',
    'summary': 'Generate recurring invoices and manage renewals',
    'description': """
This module allows you to manage subscriptions.

Features:
    - Create & edit subscriptions
    - Modify subscriptions with sales orders
    - Generate invoice automatically at fixed intervals
""",
    'author': 'Camptocamp / Odoo',
    'website': 'https://www.odoo.com/page/subscriptions',
    'depends': [
        'sale_management',
        'portal',
        'web_cohort',
        'rating',
        'base_automation',
        'sms',
    ],
    'data': [
        'security/sale_subscription_security.xml',
        'security/ir.model.access.csv',
        'security/sms_security.xml',
        'wizard/sale_subscription_close_reason_wizard_views.xml',
        'wizard/sale_subscription_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/sale_subscription_views.xml',
        'views/account_analytic_account_views.xml',
        'views/assets.xml',
        'views/subscription_portal_templates.xml',
        'views/mail_activity_views.xml',
        'data/mail_template_data.xml',
        'data/sale_subscription_data.xml',
        'data/sms_template_data.xml',
        'report/sale_subscription_report_view.xml',
    ],
    'demo': [
        'data/sale_subscription_demo.xml'
    ],
    'application': True,
    'license': 'OEEL-1',
}
