# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name' : 'Sale BE Intrastat Bridge',
    'category': 'Accounting/Accounting',
    'description': """
        Bridge module between sale_intrastat and l10n_be_intrastat.
    """,
    'depends': ['sale_intrastat', 'l10n_be_intrastat'],
    'auto_install': True,
    'license': 'OEEL-1',
}
