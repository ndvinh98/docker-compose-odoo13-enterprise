# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Amazon/Delivery Bridge",
    'summary': "Bridge module between Amazon Connector and Delivery",
    'description': """
Allows to use tracking numbers for products sold on Amazon
==========================================================
""",
    'category': 'Sales/Sales',
    'version': '1.0',
    'depends': ['sale_amazon', 'delivery'],
    'application': False,
    'auto_install': True,
}
