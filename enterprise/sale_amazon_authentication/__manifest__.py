# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Amazon/Authentication Patch",
    'summary': "Patch module for the authentication flow of the Amazon Connector",
    'description': """
This module enforces the 'public applications' authentication flow which relies on the Seller ID and
on the Authorization Token, rather than on the Seller ID, Access Key and Secret Key of the 'private
applications' flow implemented by the module sale_amazon.
""",
    'category': 'Sales/Sales',
    'version': '1.0',
    'depends': ['sale_amazon'],
    'application': False,
    'auto_install': True,
    'data': [
        'data/amazon_data.xml',
        'views/amazon_account_views.xml',
    ],
}
