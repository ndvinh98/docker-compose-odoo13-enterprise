# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Norwegian Standard Audit File for Tax',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'description': """
    Norwegian SAF-T is standard file format for exporting various types of accounting transactional data using the XML format.
    The first version of the SAF-T Financial is limited to the general ledger level including customer and supplier transactions.
    Necessary master data is also included.
    """,
    'depends': [
        'l10n_no', 'account_saft',
    ],
    'data': [
        'data/ir_cron_data.xml',
        'views/saft_report_templates.xml'
    ],
    'license': 'OEEL-1',
    'auto_install': True,
}
