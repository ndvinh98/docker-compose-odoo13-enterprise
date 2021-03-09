# -*- coding: utf-8 -*-
{
    'name': "TaxCloud and Delivery - Ecommerce",
    'summary': """Compute taxes with TaxCloud after online delivery computation.""",
    'description': """This module ensures that when delivery price is computed online, and taxes are computed with TaxCloud, the tax computation is done correctly on both the order and delivery.
    """,
    'category': 'Accounting/Accounting',
    'depends': ['website_sale_delivery', 'website_sale_account_taxcloud'],
    'data': [
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
